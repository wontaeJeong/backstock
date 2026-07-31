from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from shutil import copytree

import polars as pl
import pytest

from packages.domain.market_data import (
    AdjustmentMode,
    Bar,
    BarRequest,
    DataLineage,
    Instrument,
    MarketDataResult,
)
from packages.market_data.snapshots import FileSnapshotStore, SnapshotIntegrityError
from packages.market_data.validation import DatasetValidationInput, validate_dataset


def _request() -> BarRequest:
    return BarRequest(
        instrument=Instrument(
            instrument_id="US:XNAS:AAPL",
            symbol="AAPL",
            exchange="XNAS",
            currency="USD",
            timezone="America/New_York",
        ),
        start=datetime(2024, 1, 2, tzinfo=UTC),
        end=datetime(2024, 1, 4, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )


def _result() -> MarketDataResult[Bar]:
    bars = tuple(
        Bar(
            instrument_id="US:XNAS:AAPL",
            timestamp=datetime(2024, 1, day, tzinfo=UTC),
            open=Decimal("100.10"),
            high=Decimal("102.20"),
            low=Decimal("99.90"),
            close=Decimal("101.50"),
            volume=12345,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        )
        for day in (2, 3)
    )
    return MarketDataResult(
        items=bars,
        lineage=DataLineage(
            provider="fixture",
            provider_version="1.0",
            acquired_at=datetime(2024, 1, 5, tzinfo=UTC),
            request_options=(("provider_symbol", "AAPL"), ("interval", "1d")),
            raw_checksum="sha256:raw",
            raw_payload_path="raw/payload",
            raw_metadata_path="raw/metadata.json",
        ),
    )


def test_snapshot_publication_is_deterministic_and_retrievable(tmp_path: Path) -> None:
    # Given
    request = _request()
    result = _result()
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    store = FileSnapshotStore(tmp_path)

    # When
    first = store.publish(request=request, result=result, report=report)
    second = store.publish(request=request, result=result, report=report)
    loaded = store.load(first.snapshot_id)

    # Then
    assert first == second == loaded
    assert first.normalized_checksum.startswith("sha256:")
    assert first.price_adjustment is AdjustmentMode.RAW
    assert first.volume_adjustment is AdjustmentMode.RAW
    assert first.row_count == 2
    normalized_name = f"{first.normalized_checksum.removeprefix('sha256:')}.parquet"
    normalized = tmp_path / "normalized" / normalized_name
    assert normalized.read_bytes()[:4] == b"PAR1"
    assert first.storage_uri.startswith("snapshot://normalized/")


def test_snapshot_load_rejects_modified_normalized_data(tmp_path: Path) -> None:
    # Given
    request = _request()
    result = _result()
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    store = FileSnapshotStore(tmp_path)
    manifest = store.publish(request=request, result=result, report=report)
    normalized_name = f"{manifest.normalized_checksum.removeprefix('sha256:')}.parquet"
    normalized = tmp_path / "normalized" / normalized_name
    _ = normalized.write_bytes(b"tampered")

    # When / Then
    with pytest.raises(SnapshotIntegrityError):
        _ = store.load(manifest.snapshot_id)


def test_snapshot_load_rejects_modified_manifest_metadata(tmp_path: Path) -> None:
    request = _request()
    result = _result()
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    store = FileSnapshotStore(tmp_path)
    manifest = store.publish(request=request, result=result, report=report)
    manifest_path = tmp_path / "snapshots" / f"{manifest.snapshot_id}.json"
    metadata = manifest_path.read_text()
    _ = manifest_path.write_text(
        metadata.replace('"provider_version": "1.0"', '"provider_version": "tampered"')
    )

    with pytest.raises(SnapshotIntegrityError):
        _ = store.load(manifest.snapshot_id)


def test_refreshed_acquisition_creates_a_new_snapshot(tmp_path: Path) -> None:
    request = _request()
    result = _result()
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    store = FileSnapshotStore(tmp_path)
    refreshed = result.model_copy(
        update={
            "lineage": result.lineage.model_copy(
                update={"acquired_at": datetime(2024, 1, 6, tzinfo=UTC)}
            )
        }
    )

    first = store.publish(request=request, result=result, report=report)
    second = store.publish(request=request, result=refreshed, report=report)

    assert first.snapshot_id != second.snapshot_id
    assert store.load(first.snapshot_id) == first
    assert store.load(second.snapshot_id) == second


def test_snapshot_lookup_does_not_resolve_untrusted_paths(tmp_path: Path) -> None:
    # Given
    store = FileSnapshotStore(tmp_path / "store")
    (tmp_path / "store" / "secret.json").parent.mkdir(parents=True)
    _ = (tmp_path / "store" / "secret.json").write_text("secret")

    # When
    loaded = store.load("../secret")

    # Then
    assert loaded is None


def test_snapshot_identity_survives_storage_relocation(tmp_path: Path) -> None:
    request = _request()
    result = _result()
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    manifest = FileSnapshotStore(source).publish(request=request, result=result, report=report)
    _ = copytree(source, destination)

    relocated = FileSnapshotStore(destination).load(manifest.snapshot_id)

    assert relocated == manifest


def test_snapshot_parquet_preserves_fractional_precision(tmp_path: Path) -> None:
    request = _request()
    precise = Decimal("1.1234567890123456789")
    result = _result().model_copy(
        update={
            "items": tuple(
                bar.model_copy(
                    update={"open": precise, "high": precise, "low": precise, "close": precise}
                )
                for bar in _result().items
            )
        }
    )
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    manifest = FileSnapshotStore(tmp_path).publish(request=request, result=result, report=report)
    normalized_name = f"{manifest.normalized_checksum.removeprefix('sha256:')}.parquet"
    normalized = tmp_path / "normalized" / normalized_name

    frame = pl.read_parquet(BytesIO(normalized.read_bytes()))

    assert frame["open"].to_list() == [precise, precise]


def test_snapshot_manifest_rejects_noncanonical_storage_uri(tmp_path: Path) -> None:
    request = _request()
    result = _result()
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))
    store = FileSnapshotStore(tmp_path)
    manifest = store.publish(request=request, result=result, report=report)
    manifest_path = tmp_path / "snapshots" / f"{manifest.snapshot_id}.json"
    metadata = manifest_path.read_text()
    _ = manifest_path.write_text(
        metadata.replace(manifest.storage_uri, "file:///private/internal/data.parquet")
    )

    with pytest.raises(SnapshotIntegrityError):
        _ = store.load(manifest.snapshot_id)


def test_snapshot_preserves_distinct_price_and_volume_adjustments(tmp_path: Path) -> None:
    request = _request().model_copy(update={"adjustment": AdjustmentMode.TOTAL_RETURN_ADJUSTED})
    result = _result().model_copy(
        update={
            "items": tuple(
                bar.model_copy(update={"price_adjustment": AdjustmentMode.TOTAL_RETURN_ADJUSTED})
                for bar in _result().items
            )
        }
    )
    report = validate_dataset(DatasetValidationInput(request=request, bars=result.items))

    manifest = FileSnapshotStore(tmp_path).publish(request=request, result=result, report=report)
    normalized_name = f"{manifest.normalized_checksum.removeprefix('sha256:')}.parquet"
    frame = pl.read_parquet(tmp_path / "normalized" / normalized_name)

    assert manifest.price_adjustment is AdjustmentMode.TOTAL_RETURN_ADJUSTED
    assert manifest.volume_adjustment is AdjustmentMode.RAW
    assert frame["price_adjustment"].to_list() == ["total_return_adjusted"] * 2
    assert frame["volume_adjustment"].to_list() == ["raw"] * 2
