from dataclasses import dataclass
from datetime import UTC
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import ClassVar, Final

import polars as pl

from packages.domain.market_data import (
    AdjustmentMode,
    Bar,
    BarRequest,
    CorporateAction,
    ExchangeCalendarRequest,
    ExchangeSession,
    Instrument,
    InstrumentSearchRequest,
    MarketDataResult,
    ProviderCapabilities,
    TimestampProvenance,
)
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.normalization import BarNormalization, bars_from_csv, bars_from_frame
from packages.market_data.provider_support import lineage, not_supported
from packages.market_data.raw_store import FileRawStore

INSTRUMENT_MISMATCH: Final = "request instrument does not match the local dataset"
ADJUSTMENT_MISMATCH: Final = "request adjustment does not match the local dataset"
INVALID_PARQUET: Final = "local Parquet file could not be decoded"
INVALID_EXTENSION: Final = "local data file must be CSV or Parquet"
PARQUET_COLUMN_LIMIT: Final = "local Parquet column limit exceeded"


class LocalFileSelection(StrEnum):
    REQUEST_RANGE = "request_range"
    FULL_SOURCE = "full_source"


@dataclass(frozen=True, slots=True)
class LocalFileSource:
    path: Path
    source_name: str
    instrument: Instrument
    price_adjustment: AdjustmentMode
    volume_adjustment: AdjustmentMode
    max_rows: int = 1_000_000
    max_columns: int = 32
    selection: LocalFileSelection = LocalFileSelection.REQUEST_RANGE


class LocalFileProvider:
    name: ClassVar[str] = "local_file"
    version: ClassVar[str] = "1"

    _source: LocalFileSource
    _raw_store: FileRawStore

    def __init__(self, source: LocalFileSource, *, raw_store: FileRawStore) -> None:
        """Bind one local dataset to explicit instrument and adjustment metadata."""
        self._source = source
        self._raw_store = raw_store

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            daily_bars=True,
            corporate_actions=False,
            instrument_search=False,
            exchange_calendar=False,
        )

    def get_bars(self, request: BarRequest) -> MarketDataResult[Bar]:
        if request.instrument.instrument_id != self._source.instrument.instrument_id:
            raise self._invalid(INSTRUMENT_MISMATCH)
        if request.adjustment is not self._source.price_adjustment:
            raise self._invalid(ADJUSTMENT_MISMATCH)
        try:
            payload = self._source.path.read_bytes()
        except OSError as error:
            raise MarketDataError(
                provider=self.name,
                category=ProviderErrorCategory.INVALID_REQUEST,
                message="local market data file could not be read",
                retryable=False,
            ) from error
        bars, media_type = self._normalize(payload)
        if request.interval != "1d" and any(
            bar.timestamp_provenance is not TimestampProvenance.EXPLICIT_OFFSET for bar in bars
        ):
            msg = "intraday timestamps require explicit UTC offsets and close labels"
            raise self._invalid(msg)
        artifact = self._raw_store.capture(
            provider=self.name,
            provider_version=self.version,
            request={
                "source_name": self._source.source_name,
                "instrument_id": self._source.instrument.instrument_id,
                "provider_symbol": self._source.instrument.symbol,
                "timezone": self._source.instrument.timezone,
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "interval": request.interval,
                "timestamp_label": "close" if request.interval != "1d" else "session_date",
                "price_adjustment": self._source.price_adjustment.value,
                "volume_adjustment": self._source.volume_adjustment.value,
                "adjustment_vintage": "static_file",
            },
            payload=payload,
            media_type=media_type,
        )
        start = request.start.astimezone(UTC)
        end = request.end.astimezone(UTC)
        match self._source.selection:
            case LocalFileSelection.REQUEST_RANGE:
                selected = tuple(
                    bar for bar in bars if start <= bar.timestamp.astimezone(UTC) < end
                )
            case LocalFileSelection.FULL_SOURCE:
                selected = bars
        return MarketDataResult(items=selected, lineage=lineage(artifact))

    def get_corporate_actions(self, request: BarRequest) -> MarketDataResult[CorporateAction]:
        del request
        raise not_supported(self.name, "corporate actions")

    def search_instruments(self, request: InstrumentSearchRequest) -> MarketDataResult[Instrument]:
        del request
        raise not_supported(self.name, "instrument search")

    def get_exchange_calendar(
        self, request: ExchangeCalendarRequest
    ) -> MarketDataResult[ExchangeSession]:
        del request
        raise not_supported(self.name, "exchange calendars")

    def _normalize(self, payload: bytes) -> tuple[tuple[Bar, ...], str]:
        normalization = BarNormalization(
            instrument=self._source.instrument,
            price_adjustment=self._source.price_adjustment,
            volume_adjustment=self._source.volume_adjustment,
            provider=self.name,
            max_rows=self._source.max_rows,
        )
        if self._source.path.suffix.casefold() == ".csv":
            bars = bars_from_csv(payload, normalization=normalization)
            return bars, "text/csv"
        if self._source.path.suffix.casefold() == ".parquet":
            frame = self._parquet_frame(payload)
            bars = bars_from_frame(frame, normalization=normalization)
            return bars, "application/vnd.apache.parquet"
        raise self._invalid(INVALID_EXTENSION)

    def _parquet_frame(self, payload: bytes) -> pl.DataFrame:
        if not payload.startswith(b"PAR1") or not payload.endswith(b"PAR1"):
            raise self._invalid(INVALID_PARQUET)
        try:
            schema = pl.read_parquet_schema(BytesIO(payload))
        except (OSError, pl.exceptions.PolarsError) as error:
            raise self._invalid(INVALID_PARQUET) from error
        if len(schema) > self._source.max_columns:
            raise self._invalid(PARQUET_COLUMN_LIMIT)
        columns = ["timestamp", "open", "high", "low", "close", "volume"]
        if "open" not in schema:
            try:
                timestamp = next(name for name in ("Date", "Datetime") if name in schema)
            except StopIteration as error:
                raise self._invalid(INVALID_PARQUET) from error
            columns = [timestamp, "Open", "High", "Low", "Close", "Volume"]
        try:
            return pl.read_parquet(
                BytesIO(payload),
                columns=columns,
                n_rows=self._source.max_rows + 1,
            )
        except (OSError, pl.exceptions.PolarsError) as error:
            raise self._invalid(INVALID_PARQUET) from error

    def _invalid(self, message: str) -> MarketDataError:
        return MarketDataError(
            provider=self.name,
            category=ProviderErrorCategory.INVALID_REQUEST,
            message=message,
            retryable=False,
        )
