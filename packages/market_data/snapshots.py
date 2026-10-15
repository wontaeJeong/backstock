import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import ClassVar, Final, Protocol, override

import polars as pl
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from packages.domain.market_data import AdjustmentMode, Bar, BarRequest, MarketDataResult
from packages.market_data.artifacts import publish_immutable
from packages.market_data.raw_store import RequestOptions
from packages.market_data.validation import (
    ValidationIssue,
    ValidationReport,
    ValidationStatus,
    parquet_decimal_scale,
)

SNAPSHOT_SCHEMA_VERSION: Final = "bars.v1"


class SnapshotManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    snapshot_id: str
    provider: str
    provider_version: str
    acquired_at: datetime
    query_options: RequestOptions
    provider_symbol: str
    canonical_symbol: str
    instrument_id: str
    interval: str
    range_start: datetime
    range_end: datetime
    timezone: str
    currency: str | None = None
    price_adjustment: AdjustmentMode
    volume_adjustment: AdjustmentMode
    row_count: int
    raw_checksum: str
    normalized_checksum: str
    schema_version: str
    validation_status: ValidationStatus
    warnings: tuple[ValidationIssue, ...]
    storage_uri: str
    manifest_uri: str


@dataclass(frozen=True, slots=True)
class SnapshotIntegrityError(Exception):
    snapshot_id: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"snapshot {self.snapshot_id} failed integrity validation: {self.reason}"


@dataclass(frozen=True, slots=True)
class InvalidSnapshotPublicationError(Exception):
    status: ValidationStatus

    @override
    def __str__(self) -> str:
        return f"cannot publish dataset with validation status {self.status}"


class SnapshotStore(Protocol):
    def publish(
        self,
        *,
        request: BarRequest,
        result: MarketDataResult[Bar],
        report: ValidationReport,
    ) -> SnapshotManifest: ...

    def load(self, snapshot_id: str) -> SnapshotManifest | None: ...


class FileSnapshotStore:
    _normalized_root: Path
    _manifest_root: Path

    def __init__(self, root: Path) -> None:
        """Create separated content-addressed normalized and manifest roots."""
        resolved = root.resolve()
        self._normalized_root = resolved / "normalized"
        self._manifest_root = resolved / "snapshots"

    def publish(
        self,
        *,
        request: BarRequest,
        result: MarketDataResult[Bar],
        report: ValidationReport,
    ) -> SnapshotManifest:
        if report.status is ValidationStatus.INVALID:
            raise InvalidSnapshotPublicationError(report.status)
        parquet = _parquet_bytes(result.items)
        normalized_checksum = _checksum(parquet)
        normalized_name = f"{normalized_checksum.removeprefix('sha256:')}.parquet"
        normalized_path = self._normalized_root / normalized_name
        options = dict(result.lineage.request_options)
        draft = SnapshotManifest(
            snapshot_id="",
            provider=result.lineage.provider,
            provider_version=result.lineage.provider_version,
            acquired_at=result.lineage.acquired_at,
            query_options=result.lineage.request_options,
            provider_symbol=str(options.get("provider_symbol", request.instrument.symbol)),
            canonical_symbol=request.instrument.symbol,
            instrument_id=request.instrument.instrument_id,
            interval=str(options.get("interval", "1d")),
            range_start=request.start,
            range_end=request.end,
            timezone=request.instrument.timezone,
            currency=request.instrument.currency,
            price_adjustment=result.items[0].price_adjustment,
            volume_adjustment=result.items[0].volume_adjustment,
            row_count=len(result.items),
            raw_checksum=result.lineage.raw_checksum,
            normalized_checksum=normalized_checksum,
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            validation_status=report.status,
            warnings=report.issues,
            storage_uri=f"snapshot://normalized/{normalized_name}",
            manifest_uri="",
        )
        snapshot_id = hashlib.sha256(_canonical_json(_manifest_identity(draft))).hexdigest()
        manifest_path = self._manifest_root / f"{snapshot_id}.json"
        manifest = draft.model_copy(
            update={
                "snapshot_id": snapshot_id,
                "manifest_uri": f"snapshot://manifests/{snapshot_id}.json",
            }
        )
        self._normalized_root.mkdir(parents=True, exist_ok=True)
        self._manifest_root.mkdir(parents=True, exist_ok=True)
        _write_once(normalized_path, parquet)
        _write_once(manifest_path, manifest.model_dump_json(indent=2).encode())
        return manifest

    def load(self, snapshot_id: str) -> SnapshotManifest | None:
        if re.fullmatch(r"[0-9a-f]{64}", snapshot_id) is None:
            return None
        manifest_path = self._manifest_root / f"{snapshot_id}.json"
        if not manifest_path.is_file():
            return None
        try:
            manifest = SnapshotManifest.model_validate_json(manifest_path.read_bytes())
            expected_name = f"{manifest.normalized_checksum.removeprefix('sha256:')}.parquet"
            expected_storage_uri = f"snapshot://normalized/{expected_name}"
            if manifest.storage_uri != expected_storage_uri:
                raise SnapshotIntegrityError(snapshot_id, "normalized storage URI differs")
            normalized_path = self._normalized_root / expected_name
            normalized = normalized_path.read_bytes()
        except (OSError, ValidationError) as error:
            raise SnapshotIntegrityError(
                snapshot_id, "manifest or Parquet cannot be read"
            ) from error
        if manifest.snapshot_id != snapshot_id:
            raise SnapshotIntegrityError(snapshot_id, "manifest identity differs")
        expected_id = hashlib.sha256(_canonical_json(_manifest_identity(manifest))).hexdigest()
        expected_manifest_uri = f"snapshot://manifests/{snapshot_id}.json"
        if expected_id != snapshot_id or manifest.manifest_uri != expected_manifest_uri:
            raise SnapshotIntegrityError(snapshot_id, "manifest metadata differs")
        if _checksum(normalized) != manifest.normalized_checksum:
            raise SnapshotIntegrityError(snapshot_id, "normalized checksum differs")
        return manifest

    def read_bars(self, snapshot_id: str) -> tuple[SnapshotManifest, tuple[Bar, ...]] | None:
        """Decode only bytes bound to a validated immutable manifest."""
        manifest = self.load(snapshot_id)
        if manifest is None:
            return None
        name = f"{manifest.normalized_checksum.removeprefix('sha256:')}.parquet"
        payload = (self._normalized_root / name).read_bytes()
        if _checksum(payload) != manifest.normalized_checksum:
            raise SnapshotIntegrityError(snapshot_id, "normalized checksum changed")
        frame = pl.read_parquet(BytesIO(payload))
        bars = tuple(Bar.model_validate(row) for row in frame.to_dicts())
        if len(bars) != manifest.row_count:
            raise SnapshotIntegrityError(snapshot_id, "row count differs")
        return manifest, bars


def _parquet_bytes(bars: tuple[Bar, ...]) -> bytes:
    ordered = sorted(bars, key=lambda bar: (bar.timestamp, bar.instrument_id))
    decimal_scale = parquet_decimal_scale(bars)
    if decimal_scale is None:
        raise InvalidSnapshotPublicationError(ValidationStatus.INVALID)
    frame = pl.DataFrame(
        {
            "instrument_id": [bar.instrument_id for bar in ordered],
            "timestamp": [bar.timestamp for bar in ordered],
            "open": [bar.open for bar in ordered],
            "high": [bar.high for bar in ordered],
            "low": [bar.low for bar in ordered],
            "close": [bar.close for bar in ordered],
            "volume": [bar.volume for bar in ordered],
            "price_adjustment": [bar.price_adjustment.value for bar in ordered],
            "volume_adjustment": [bar.volume_adjustment.value for bar in ordered],
            "timestamp_provenance": [bar.timestamp_provenance.value for bar in ordered],
        },
        schema_overrides={
            "open": pl.Decimal(precision=38, scale=decimal_scale),
            "high": pl.Decimal(precision=38, scale=decimal_scale),
            "low": pl.Decimal(precision=38, scale=decimal_scale),
            "close": pl.Decimal(precision=38, scale=decimal_scale),
        },
    )
    if any(bar.bid is not None for bar in ordered):
        frame = frame.with_columns(
            pl.Series("bid", [bar.bid for bar in ordered], dtype=pl.Decimal(38, decimal_scale)),
            pl.Series("ask", [bar.ask for bar in ordered], dtype=pl.Decimal(38, decimal_scale)),
        )
    stream = BytesIO()
    frame.write_parquet(
        stream,
        compression="zstd",
        compression_level=3,
        statistics=False,
        row_group_size=max(1, len(ordered)),
    )
    return stream.getvalue()


def _checksum(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _canonical_json(value: JsonValue) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _manifest_identity(manifest: SnapshotManifest) -> dict[str, JsonValue]:
    identity: dict[str, JsonValue] = {
        "provider": manifest.provider,
        "provider_version": manifest.provider_version,
        "acquired_at": manifest.acquired_at.isoformat(),
        "query_options": [list(option) for option in manifest.query_options],
        "provider_symbol": manifest.provider_symbol,
        "canonical_symbol": manifest.canonical_symbol,
        "instrument_id": manifest.instrument_id,
        "interval": manifest.interval,
        "range_start": manifest.range_start.isoformat(),
        "range_end": manifest.range_end.isoformat(),
        "timezone": manifest.timezone,
        "price_adjustment": manifest.price_adjustment.value,
        "volume_adjustment": manifest.volume_adjustment.value,
        "row_count": manifest.row_count,
        "raw_checksum": manifest.raw_checksum,
        "normalized_checksum": manifest.normalized_checksum,
        "schema_version": manifest.schema_version,
        "validation_status": manifest.validation_status.value,
        "warnings": [
            {
                "code": warning.code.value,
                "severity": warning.severity.value,
                "message": warning.message,
            }
            for warning in manifest.warnings
        ],
        "storage_uri": manifest.storage_uri,
    }
    if manifest.currency is not None:
        identity["currency"] = manifest.currency
    return identity


def _write_once(path: Path, content: bytes) -> None:
    if not publish_immutable(path, content):
        raise SnapshotIntegrityError(path.stem, "write-once artifact collision")
