"""Static operator/indicator descriptors for building strategy editor UIs."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class OperatorMetadata:
    name: str
    category: str
    arity: str
    description: str


@dataclass(frozen=True, slots=True)
class IndicatorMetadata:
    name: str
    parameters: tuple[str, ...]
    minimum_lookback: str
    output_type: str
    availability: str
    description: str


OPERATORS: Final[tuple[OperatorMetadata, ...]] = (
    OperatorMetadata("all", "logical", "n-ary", "true when every child condition is true"),
    OperatorMetadata("any", "logical", "n-ary", "true when at least one child condition is true"),
    OperatorMetadata("not", "logical", "unary", "negates a single child condition"),
    OperatorMetadata("gt", "comparison", "binary", "left is strictly greater than right"),
    OperatorMetadata("gte", "comparison", "binary", "left is greater than or equal to right"),
    OperatorMetadata("lt", "comparison", "binary", "left is strictly less than right"),
    OperatorMetadata("lte", "comparison", "binary", "left is less than or equal to right"),
    OperatorMetadata("eq", "comparison", "binary", "left equals right"),
    OperatorMetadata(
        "crosses_above",
        "cross",
        "binary",
        "left was less than or equal to right on the prior bar and is greater now",
    ),
    OperatorMetadata(
        "crosses_below",
        "cross",
        "binary",
        "left was greater than or equal to right on the prior bar and is less now",
    ),
)

INDICATORS: Final[tuple[IndicatorMetadata, ...]] = (
    IndicatorMetadata(
        "sma",
        ("period",),
        "period bars",
        "price",
        "close of the current bar",
        "simple moving average of close",
    ),
    IndicatorMetadata(
        "ema",
        ("period",),
        "period bars",
        "price",
        "close of the current bar",
        "exponential moving average of close, seeded with an SMA",
    ),
    IndicatorMetadata(
        "rsi",
        ("period",),
        "period + 1 bars",
        "oscillator (0-100)",
        "close of the current bar",
        "Wilder relative strength index",
    ),
    IndicatorMetadata(
        "atr",
        ("period",),
        "period + 1 bars",
        "price",
        "close of the current bar",
        "Wilder average true range",
    ),
    IndicatorMetadata(
        "rolling_high",
        ("period",),
        "period bars",
        "price",
        "close of the current bar",
        "highest high over the trailing window",
    ),
    IndicatorMetadata(
        "rolling_low",
        ("period",),
        "period bars",
        "price",
        "close of the current bar",
        "lowest low over the trailing window",
    ),
    IndicatorMetadata(
        "volume_average",
        ("period",),
        "period bars",
        "volume",
        "close of the current bar",
        "average volume over the trailing window",
    ),
    IndicatorMetadata(
        "volume_ratio",
        ("period",),
        "period + 1 bars",
        "ratio",
        "close of the current bar",
        "current volume divided by the trailing average volume",
    ),
    IndicatorMetadata(
        "return",
        ("period",),
        "period + 1 bars",
        "ratio",
        "close of the current bar",
        "close-to-close return over the trailing window",
    ),
)
