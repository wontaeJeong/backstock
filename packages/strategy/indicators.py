"""Pure indicator math over ascending single-instrument bar history."""

from collections.abc import Callable, Sequence
from decimal import Decimal
from itertools import pairwise
from typing import Final

from packages.domain.market_data import Bar

UNKNOWN_INDICATOR: Final = "unknown indicator"

_SIMPLE_WINDOW_INDICATORS: Final = frozenset(
    {
        "sma",
        "rolling_high",
        "rolling_low",
        "volume_average",
        "vwap",
        "bollinger_middle",
        "bollinger_upper",
        "bollinger_lower",
    }
)
_SMOOTHED_INDICATORS: Final = frozenset({"ema", "rsi", "atr"})


def minimum_lookback(
    indicator: str,
    period: int,
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> int:
    del fast_period
    if indicator.startswith("macd"):
        return slow_period + (0 if indicator == "macd" else signal_period - 1)
    if indicator in _SIMPLE_WINDOW_INDICATORS:
        return period
    if indicator in _SMOOTHED_INDICATORS:
        return period if indicator == "ema" else period + 1
    if indicator in {"volume_ratio", "return"}:
        return period + 1
    raise ValueError(UNKNOWN_INDICATOR)


def compute_indicator(  # noqa: PLR0913 -- explicit bounded DSL indicator parameters
    indicator: str,
    period: int,
    window: Sequence[Bar],
    *,
    stddev_multiplier: Decimal = Decimal(2),
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Decimal | None:
    if len(window) < minimum_lookback(
        indicator,
        period,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    ):
        return None
    if indicator.startswith("macd"):
        return _macd(indicator, window, fast_period, slow_period, signal_period)
    if indicator.startswith("bollinger"):
        mean = sum((b.close for b in window[-period:]), Decimal(0)) / period
        variance = sum(((b.close - mean) ** 2 for b in window[-period:]), Decimal(0)) / period
        sign = 1 if indicator == "bollinger_upper" else -1 if indicator == "bollinger_lower" else 0
        return mean + sign * stddev_multiplier * variance.sqrt()
    if indicator == "vwap":
        volume = sum(b.volume for b in window[-period:])
        return (
            sum(((b.high + b.low + b.close) / 3 * b.volume for b in window[-period:]), Decimal(0))
            / volume
            if volume
            else None
        )
    handler = _HANDLERS.get(indicator)
    if handler is None:
        raise ValueError(UNKNOWN_INDICATOR)
    return handler(window, period)


def _ema_values(values: Sequence[Decimal], period: int) -> list[Decimal]:
    value = sum(values[:period], Decimal(0)) / period
    result = [value]
    weight = Decimal(2) / (period + 1)
    for current in values[period:]:
        value += (current - value) * weight
        result.append(value)
    return result


def _macd(indicator: str, window: Sequence[Bar], fast: int, slow: int, signal: int) -> Decimal:
    closes = [bar.close for bar in window]
    fast_values = _ema_values(closes, fast)[slow - fast :]
    slow_values = _ema_values(closes, slow)
    values = [a - b for a, b in zip(fast_values, slow_values, strict=True)]
    if indicator == "macd":
        return values[-1]
    signal_value = _ema_values(values, signal)[-1]
    return signal_value if indicator == "macd_signal" else values[-1] - signal_value


def _sma(window: Sequence[Bar], period: int) -> Decimal | None:
    closes = window[-period:]
    return sum((bar.close for bar in closes), Decimal(0)) / period


def _volume_average(window: Sequence[Bar]) -> Decimal:
    return Decimal(sum(bar.volume for bar in window)) / len(window)


def _volume_average_window(window: Sequence[Bar], period: int) -> Decimal | None:
    return _volume_average(window[-period:])


def _rolling_high(window: Sequence[Bar], period: int) -> Decimal | None:
    return max(bar.high for bar in window[-period:])


def _rolling_low(window: Sequence[Bar], period: int) -> Decimal | None:
    return min(bar.low for bar in window[-period:])


def _return(window: Sequence[Bar], period: int) -> Decimal | None:
    return window[-1].close / window[-1 - period].close - 1


def _volume_ratio(window: Sequence[Bar], period: int) -> Decimal | None:
    prior = window[-1 - period : -1]
    average = _volume_average(prior)
    if average == 0:
        return None
    return Decimal(window[-1].volume) / average


def _ema(window: Sequence[Bar], period: int) -> Decimal | None:
    smoothing = Decimal(2) / (period + 1)
    value = _sma(window[:period], period)
    if value is None:
        return None
    for bar in window[period:]:
        value = bar.close * smoothing + value * (Decimal(1) - smoothing)
    return value


def _rsi(window: Sequence[Bar], period: int) -> Decimal | None:
    diffs = [current.close - previous.close for previous, current in pairwise(window)]
    seed_gain = sum((max(diff, Decimal(0)) for diff in diffs[:period]), Decimal(0)) / period
    seed_loss = sum((max(-diff, Decimal(0)) for diff in diffs[:period]), Decimal(0)) / period
    average_gain, average_loss = seed_gain, seed_loss
    for diff in diffs[period:]:
        gain = max(diff, Decimal(0))
        loss = max(-diff, Decimal(0))
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        return Decimal(100)
    relative_strength = average_gain / average_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + relative_strength)


def _true_range(previous: Bar, current: Bar) -> Decimal:
    return max(
        current.high - current.low,
        abs(current.high - previous.close),
        abs(current.low - previous.close),
    )


def _atr(window: Sequence[Bar], period: int) -> Decimal | None:
    ranges = [_true_range(previous, current) for previous, current in pairwise(window)]
    value = sum(ranges[:period], Decimal(0)) / period
    for true_range in ranges[period:]:
        value = (value * (period - 1) + true_range) / period
    return value


_HANDLERS: Final[dict[str, Callable[[Sequence[Bar], int], Decimal | None]]] = {
    "sma": _sma,
    "ema": _ema,
    "rsi": _rsi,
    "atr": _atr,
    "rolling_high": _rolling_high,
    "rolling_low": _rolling_low,
    "volume_average": _volume_average_window,
    "volume_ratio": _volume_ratio,
    "return": _return,
}
