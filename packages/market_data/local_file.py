from datetime import UTC
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
)
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.normalization import bars_from_csv
from packages.market_data.provider_support import lineage, not_supported
from packages.market_data.raw_store import FileRawStore

INSTRUMENT_MISMATCH: Final = "request instrument does not match the local dataset"
ADJUSTMENT_MISMATCH: Final = "request adjustment does not match the local dataset"
INVALID_PARQUET: Final = "local Parquet file could not be decoded"
INVALID_EXTENSION: Final = "local data file must be CSV or Parquet"


class LocalFileProvider:
    name: ClassVar[str] = "local_file"
    version: ClassVar[str] = "1"

    _path: Path
    _instrument: Instrument
    _price_adjustment: AdjustmentMode
    _volume_adjustment: AdjustmentMode
    _raw_store: FileRawStore

    def __init__(
        self,
        *,
        path: Path,
        instrument: Instrument,
        price_adjustment: AdjustmentMode,
        volume_adjustment: AdjustmentMode,
        raw_store: FileRawStore,
    ) -> None:
        """Bind one local dataset to explicit instrument and adjustment metadata."""
        self._path = path
        self._instrument = instrument
        self._price_adjustment = price_adjustment
        self._volume_adjustment = volume_adjustment
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
        if request.instrument.instrument_id != self._instrument.instrument_id:
            raise self._invalid(INSTRUMENT_MISMATCH)
        if request.adjustment is not self._price_adjustment:
            raise self._invalid(ADJUSTMENT_MISMATCH)
        try:
            payload = self._path.read_bytes()
        except OSError as error:
            raise MarketDataError(
                provider=self.name,
                category=ProviderErrorCategory.INVALID_REQUEST,
                message="local market data file could not be read",
                retryable=False,
            ) from error
        normalized_csv, media_type = self._normalization_payload(payload)
        artifact = self._raw_store.capture(
            provider=self.name,
            provider_version=self.version,
            request={
                "path": str(self._path),
                "instrument_id": self._instrument.instrument_id,
                "provider_symbol": self._instrument.symbol,
                "timezone": self._instrument.timezone,
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "interval": "1d",
                "price_adjustment": self._price_adjustment.value,
                "volume_adjustment": self._volume_adjustment.value,
                "adjustment_vintage": "static_file",
            },
            payload=payload,
            media_type=media_type,
        )
        bars = bars_from_csv(
            normalized_csv,
            instrument=self._instrument,
            price_adjustment=self._price_adjustment,
            volume_adjustment=self._volume_adjustment,
            provider=self.name,
        )
        start = request.start.astimezone(UTC)
        end = request.end.astimezone(UTC)
        selected = tuple(bar for bar in bars if start <= bar.timestamp.astimezone(UTC) < end)
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

    def _normalization_payload(self, payload: bytes) -> tuple[bytes, str]:
        if self._path.suffix.casefold() == ".csv":
            return payload, "text/csv"
        if self._path.suffix.casefold() == ".parquet":
            try:
                frame = pl.read_parquet(BytesIO(payload))
                return frame.write_csv().encode(), "application/vnd.apache.parquet"
            except Exception as error:
                raise self._invalid(INVALID_PARQUET) from error
        raise self._invalid(INVALID_EXTENSION)

    def _invalid(self, message: str) -> MarketDataError:
        return MarketDataError(
            provider=self.name,
            category=ProviderErrorCategory.INVALID_REQUEST,
            message=message,
            retryable=False,
        )
