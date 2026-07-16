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
)
from packages.market_data.errors import MarketDataError, ProviderErrorCategory

MISSING_COLUMN: Final = "missing a required market data column"
INVALID_TIMESTAMP: Final = "timestamp must be a string or datetime"
INVALID_DECIMAL: Final = "numeric value is not a valid decimal"
NON_INTEGER_VOLUME: Final = "volume must be an integer"


def bars_from_csv(
    payload: bytes,
    *,
    instrument: Instrument,
    price_adjustment: AdjustmentMode,
    volume_adjustment: AdjustmentMode,
    provider: str,
) -> tuple[Bar, ...]:
    try:
        frame = pl.read_csv(BytesIO(payload), infer_schema=False)
        timestamp_column = _first_column(frame, ("timestamp", "Date", "Datetime"))
        columns = [timestamp_column, "Open", "High", "Low", "Close", "Volume"]
        if "open" in frame.columns:
            columns = ["timestamp", "open", "high", "low", "close", "volume"]
        rows: list[Bar] = []
        for raw_row in frame.select(columns).iter_rows():
            timestamp, open_, high, low, close, volume = cast("tuple[object, ...]", raw_row)
            rows.append(
                Bar(
                    instrument_id=instrument.instrument_id,
                    timestamp=_timestamp(timestamp, instrument.timezone),
                    open=_decimal(open_),
                    high=_decimal(high),
                    low=_decimal(low),
                    close=_decimal(close),
                    volume=_integer(volume),
                    price_adjustment=price_adjustment,
                    volume_adjustment=volume_adjustment,
                )
            )
        return tuple(sorted(rows, key=lambda bar: bar.timestamp))
    except MarketDataError:
        raise
    except Exception as error:
        raise MarketDataError(
            provider=provider,
            category=ProviderErrorCategory.PARSE,
            message="provider payload could not be normalized as daily bars",
            retryable=False,
        ) from error


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
            effective_at = _timestamp(timestamp, instrument.timezone)
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


def _timestamp(value: object, timezone: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError(INVALID_TIMESTAMP)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed


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
