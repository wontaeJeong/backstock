from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

INVALID_TIMEZONE: Final = "timezone must be a valid IANA name"
UNAWARE_TIMESTAMP: Final = "timestamp must be timezone-aware"
UNAWARE_ACTION: Final = "effective_at must be timezone-aware"
UNAWARE_BOUND: Final = "request bounds must be timezone-aware"
EMPTY_INTERVAL: Final = "end must be after start"
UNAWARE_SESSION: Final = "session hours must be timezone-aware"
INVALID_SESSION: Final = "session close must be after open"


class AdjustmentMode(StrEnum):
    RAW = "raw"
    SPLIT_ADJUSTED = "split_adjusted"
    TOTAL_RETURN_ADJUSTED = "total_return_adjusted"


class TimestampProvenance(StrEnum):
    EXPLICIT_OFFSET = "explicit_offset"
    INFERRED_FROM_INSTRUMENT = "inferred_from_instrument"


class CorporateActionKind(StrEnum):
    CASH_DIVIDEND = "cash_dividend"
    SPLIT = "split"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class Instrument(_FrozenModel):
    instrument_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=50)
    exchange: str = Field(min_length=1, max_length=50)
    currency: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=200)

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_iana(cls, value: str) -> str:
        try:
            _ = ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(INVALID_TIMEZONE) from error
        return value


class Bar(_FrozenModel):
    instrument_id: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    price_adjustment: AdjustmentMode
    volume_adjustment: AdjustmentMode
    timestamp_provenance: TimestampProvenance = TimestampProvenance.EXPLICIT_OFFSET

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(UNAWARE_TIMESTAMP)
        return value


class CorporateAction(_FrozenModel):
    instrument_id: str
    effective_at: datetime
    kind: CorporateActionKind
    value: Decimal = Field(gt=0)
    currency: str | None = None

    @field_validator("effective_at")
    @classmethod
    def effective_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(UNAWARE_ACTION)
        return value


class BarRequest(_FrozenModel):
    instrument: Instrument
    start: datetime
    end: datetime
    adjustment: AdjustmentMode

    @field_validator("start", "end")
    @classmethod
    def bounds_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(UNAWARE_BOUND)
        return value

    @model_validator(mode="after")
    def interval_must_be_nonempty(self) -> "BarRequest":
        if self.end <= self.start:
            raise ValueError(EMPTY_INTERVAL)
        return self


class InstrumentSearchRequest(_FrozenModel):
    query: str = Field(min_length=1, max_length=100)
    market: str = Field(min_length=1, max_length=20)


class ExchangeCalendarRequest(_FrozenModel):
    exchange: str = Field(min_length=1, max_length=50)
    start: date
    end: date

    @model_validator(mode="after")
    def interval_must_be_nonempty(self) -> "ExchangeCalendarRequest":
        if self.end <= self.start:
            raise ValueError(EMPTY_INTERVAL)
        return self


class ExchangeSession(_FrozenModel):
    exchange: str
    session_date: date
    opens_at: datetime
    closes_at: datetime

    @model_validator(mode="after")
    def hours_must_be_aware_and_ordered(self) -> "ExchangeSession":
        bounds = (self.opens_at, self.closes_at)
        if any(value.tzinfo is None or value.utcoffset() is None for value in bounds):
            raise ValueError(UNAWARE_SESSION)
        if self.closes_at <= self.opens_at:
            raise ValueError(INVALID_SESSION)
        return self


class ProviderCapabilities(_FrozenModel):
    daily_bars: bool
    corporate_actions: bool
    instrument_search: bool
    exchange_calendar: bool


class DataLineage(_FrozenModel):
    provider: str
    provider_version: str
    acquired_at: datetime
    request_options: tuple[tuple[str, str | bool | int | float], ...]
    raw_checksum: str
    raw_payload_path: str
    raw_metadata_path: str


class MarketDataResult[ItemT: BaseModel](_FrozenModel):
    items: tuple[ItemT, ...]
    lineage: DataLineage


def corporate_actions_are_consistent(
    bars: tuple[Bar, ...], actions: tuple[CorporateAction, ...]
) -> bool:
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    for action in actions:
        location = next(
            (index for index, bar in enumerate(ordered) if bar.timestamp >= action.effective_at),
            None,
        )
        if location is None or location == 0:
            continue
        if not _action_is_consistent(ordered[location - 1], ordered[location], action):
            return False
    return True


def _action_is_consistent(previous: Bar, current: Bar, action: CorporateAction) -> bool:
    if previous.close <= 0 or current.close <= 0:
        return False
    match action.kind:
        case CorporateActionKind.SPLIT:
            expected_price_ratio = (
                Decimal(1) / action.value
                if current.price_adjustment is AdjustmentMode.RAW
                else Decimal(1)
            )
            price_ok = abs(current.close / previous.close - expected_price_ratio) <= Decimal("0.25")
            expected_volume_ratio = (
                action.value if current.volume_adjustment is AdjustmentMode.RAW else Decimal(1)
            )
            volume_ok = previous.volume == 0 or abs(
                Decimal(current.volume) / previous.volume - expected_volume_ratio
            ) <= Decimal("0.50")
            return price_ok and volume_ok
        case CorporateActionKind.CASH_DIVIDEND:
            if current.price_adjustment is AdjustmentMode.TOTAL_RETURN_ADJUSTED:
                return abs(current.close / previous.close - 1) <= Decimal("0.25")
            tolerance = max(action.value * Decimal("0.25"), previous.close * Decimal("0.02"))
            return abs((previous.close - current.close) - action.value) <= tolerance
