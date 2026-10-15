from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Final, cast
from zoneinfo import ZoneInfo

import polars as pl

from packages.domain.market_data import (
    AdjustmentMode,
    Bar,
    CorporateAction,
    CorporateActionKind,
    Instrument,
    TimestampProvenance,
)
from packages.market_data.errors import MarketDataError, ProviderErrorCategory

MISSING_COLUMN: Final = "missing a required market data column"
INVALID_TIMESTAMP: Final = "timestamp must be a string or datetime"
INVALID_DECIMAL: Final = "numeric value is not a valid decimal"
NON_INTEGER_VOLUME: Final = "volume must be an integer"
ROW_LIMIT_EXCEEDED: Final = "market data row limit exceeded"


@dataclass(frozen=True, slots=True)
class BarNormalization:
    instrument: Instrument
    price_adjustment: AdjustmentMode
    volume_adjustment: AdjustmentMode
    provider: str
    max_rows: int = 1_000_000
    interval: str = "1d"


def bars_from_csv(
    payload: bytes,
    *,
    normalization: BarNormalization,
) -> tuple[Bar, ...]:
    try:
        frame = pl.read_csv(BytesIO(payload), infer_schema=False, n_rows=normalization.max_rows + 1)
        return bars_from_frame(frame, normalization=normalization)
    except MarketDataError:
        raise
    except Exception as error:
        raise MarketDataError(
            provider=normalization.provider,
            category=ProviderErrorCategory.PARSE,
            message="provider payload could not be normalized as daily bars",
            retryable=False,
        ) from error


def bars_from_frame(
    frame: pl.DataFrame,
    *,
    normalization: BarNormalization,
) -> tuple[Bar, ...]:
    if frame.height > normalization.max_rows:
        raise MarketDataError(
            provider=normalization.provider,
            category=ProviderErrorCategory.INVALID_REQUEST,
            message=ROW_LIMIT_EXCEEDED,
            retryable=False,
        )
    try:
        if normalization.interval == "tick":
            return _ticks_from_frame(frame, normalization)
        timestamp_column = _first_column(frame, ("timestamp", "Date", "Datetime"))
        columns = [timestamp_column, "Open", "High", "Low", "Close", "Volume"]
        if "open" in frame.columns:
            columns = ["timestamp", "open", "high", "low", "close", "volume"]
        rows: list[Bar] = []
        for raw_row in frame.select(columns).iter_rows():
            timestamp, open_, high, low, close, volume = cast("tuple[object, ...]", raw_row)
            normalized_timestamp, provenance = _timestamp(
                timestamp, normalization.instrument.timezone
            )
            rows.append(
                Bar(
                    instrument_id=normalization.instrument.instrument_id,
                    timestamp=normalized_timestamp,
                    open=_decimal(open_),
                    high=_decimal(high),
                    low=_decimal(low),
                    close=_decimal(close),
                    volume=_integer(volume),
                    price_adjustment=normalization.price_adjustment,
                    volume_adjustment=normalization.volume_adjustment,
                    timestamp_provenance=provenance,
                )
            )
        return tuple(rows)
    except MarketDataError:
        raise
    except Exception as error:
        raise MarketDataError(
            provider=normalization.provider,
            category=ProviderErrorCategory.PARSE,
            message="provider payload could not be normalized as daily bars",
            retryable=False,
        ) from error


def _ticks_from_frame(frame: pl.DataFrame, normalization: BarNormalization) -> tuple[Bar, ...]:
    if (
        normalization.price_adjustment is not AdjustmentMode.RAW
        or normalization.volume_adjustment is not AdjustmentMode.RAW
    ):
        message = "tick data must be raw"
        raise ValueError(message)
    columns = ["timestamp", "price", "size"]
    columns.extend(name for name in ("bid", "ask") if name in frame.columns)
    rows: list[Bar] = []
    for raw in frame.select(columns).iter_rows(named=True):
        timestamp, provenance = _timestamp(raw["timestamp"], normalization.instrument.timezone)
        price, size = _decimal(raw["price"]), _integer(raw["size"])
        if (
            provenance is not TimestampProvenance.EXPLICIT_OFFSET
            or not price.is_finite()
            or price <= 0
            or size < 0
            or (rows and timestamp <= rows[-1].timestamp)
        ):
            message = (
                "tick rows require aware unique ascending timestamps, "
                "positive price and nonnegative size"
            )
            raise ValueError(message)
        rows.append(
            Bar(
                instrument_id=normalization.instrument.instrument_id,
                timestamp=timestamp,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=size,
                price_adjustment=AdjustmentMode.RAW,
                volume_adjustment=AdjustmentMode.RAW,
                bid=_decimal(raw["bid"]) if raw.get("bid") is not None else None,
                ask=_decimal(raw["ask"]) if raw.get("ask") is not None else None,
            )
        )
    return tuple(rows)


def actions_from_yahoo_csv(
    payload: bytes, *, instrument: Instrument, provider: str
) -> tuple[CorporateAction, ...]:
    try:
        frame = pl.read_csv(BytesIO(payload), infer_schema=False)
        timestamp_column = _first_column(frame, ("Date", "Datetime"))
        columns = [timestamp_column, "Dividends", "Stock Splits"]
        rows: list[CorporateAction] = []
        for raw_row in frame.select(columns).iter_rows():
            timestamp, dividend, split = cast("tuple[object, ...]", raw_row)
            effective_at, _ = _timestamp(timestamp, instrument.timezone)
            dividend_value = _decimal(dividend)
            split_value = _decimal(split)
            if dividend_value > 0:
                rows.append(
                    CorporateAction(
                        instrument_id=instrument.instrument_id,
                        effective_at=effective_at,
                        kind=CorporateActionKind.CASH_DIVIDEND,
                        value=dividend_value,
                        currency=instrument.currency,
                    )
                )
            if split_value > 0:
                rows.append(
                    CorporateAction(
                        instrument_id=instrument.instrument_id,
                        effective_at=effective_at,
                        kind=CorporateActionKind.SPLIT,
                        value=split_value,
                    )
                )
        return tuple(rows)
    except Exception as error:
        raise MarketDataError(
            provider=provider,
            category=ProviderErrorCategory.PARSE,
            message="provider payload could not be normalized as corporate actions",
            retryable=False,
        ) from error


def _first_column(frame: pl.DataFrame, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise ValueError(MISSING_COLUMN)


def _timestamp(value: object, timezone: str) -> tuple[datetime, TimestampProvenance]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError(INVALID_TIMESTAMP)
    if parsed.tzinfo is None:
        return (
            parsed.replace(tzinfo=ZoneInfo(timezone)),
            TimestampProvenance.INFERRED_FROM_INSTRUMENT,
        )
    return parsed, TimestampProvenance.EXPLICIT_OFFSET


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(INVALID_DECIMAL) from error


def _integer(value: object) -> int:
    parsed = _decimal(value)
    if parsed != parsed.to_integral_value():
        raise ValueError(NON_INTEGER_VOLUME)
    return int(parsed)
