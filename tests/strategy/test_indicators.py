from datetime import UTC, datetime
from decimal import Decimal

from packages.domain.market_data import AdjustmentMode, Bar
from packages.strategy.indicators import compute_indicator, minimum_lookback


def _bar(day: int, *, high: str, low: str, close: str, volume: int = 1000) -> Bar:
    return Bar(
        instrument_id="AAA",
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


def _flat_bar(day: int, value: str, *, volume: int = 1000) -> Bar:
    return _bar(day, high=value, low=value, close=value, volume=volume)


def test_sma_averages_the_trailing_window() -> None:
    bars = [_flat_bar(day, value) for day, value in enumerate(("10", "20", "30"), start=1)]

    assert compute_indicator("sma", 3, bars) == Decimal(20)


def test_sma_is_none_before_the_window_fills() -> None:
    bars = [_flat_bar(day, value) for day, value in enumerate(("10", "20"), start=1)]

    assert compute_indicator("sma", 3, bars) is None


def test_ema_is_sma_seeded_and_recurses_forward() -> None:
    bars = [_flat_bar(day, value) for day, value in enumerate(("10", "20", "30", "40"), start=1)]

    # seed = SMA(3) of the first three closes = 20; smoothing = 2 / (3 + 1) = 0.5
    # ema = 40 * 0.5 + 20 * 0.5 = 30
    assert compute_indicator("ema", 3, bars) == Decimal(30)


def test_rsi_hits_zero_once_average_gain_collapses() -> None:
    bars = [_flat_bar(day, value) for day, value in enumerate(("100", "104", "102"), start=1)]

    # diffs = [4, -2]; period=1 seed: gain=4, loss=0
    # next diff=-2: avg_gain=(4*0+0)/1=0, avg_loss=(0*0+2)/1=2 -> RSI = 100 - 100/(1+0) = 0
    assert compute_indicator("rsi", 1, bars) == Decimal(0)


def test_rsi_matches_hand_computed_wilder_value() -> None:
    bars = [
        _flat_bar(day, value) for day, value in enumerate(("100", "104", "102", "104"), start=1)
    ]

    # diffs = [4, -2, 2]; seed (period=2): gain=(4+0)/2=2, loss=(0+2)/2=1
    # next diff=2: avg_gain=(2*1+2)/2=2, avg_loss=(1*1+0)/2=0.5 -> RS=4 -> RSI=100-100/5=80
    assert compute_indicator("rsi", 2, bars) == Decimal(80)


def test_atr_seeds_from_true_range_then_smooths() -> None:
    bars = [
        _bar(1, high="10", low="8", close="9"),
        _bar(2, high="12", low="9", close="11"),
        _bar(3, high="11", low="7", close="10"),
        _bar(4, high="14", low="10", close="13"),
    ]

    # TR1=max(3,|12-9|,|9-9|)=3; TR2=max(4,|11-11|,|7-11|)=4; TR3=max(4,|14-10|,|10-10|)=4
    # seed (period=2) = (3+4)/2 = 3.5
    assert compute_indicator("atr", 2, bars[:3]) == Decimal("3.5")
    # next TR=4: atr=(3.5*1+4)/2=3.75
    assert compute_indicator("atr", 2, bars) == Decimal("3.75")


def test_rolling_high_and_low_use_the_trailing_window() -> None:
    bars = [
        _bar(1, high="10", low="8", close="9"),
        _bar(2, high="12", low="9", close="11"),
        _bar(3, high="11", low="7", close="10"),
        _bar(4, high="14", low="10", close="13"),
    ]

    assert compute_indicator("rolling_high", 2, bars) == Decimal(14)
    assert compute_indicator("rolling_low", 2, bars) == Decimal(7)


def test_volume_average_and_ratio() -> None:
    bars = [
        _flat_bar(1, "10", volume=100),
        _flat_bar(2, "10", volume=200),
        _flat_bar(3, "10", volume=300),
        _flat_bar(4, "10", volume=400),
    ]

    assert compute_indicator("volume_average", 2, bars) == Decimal(350)
    # ratio = current volume (400) / average of the two prior bars (200, 300) = 400/250
    assert compute_indicator("volume_ratio", 2, bars) == Decimal("1.6")


def test_return_over_the_trailing_window() -> None:
    bars = [_flat_bar(day, value) for day, value in enumerate(("100", "90", "120"), start=1)]

    assert compute_indicator("return", 2, bars) == Decimal("0.2")


def test_minimum_lookback_matches_each_indicator_shape() -> None:
    assert minimum_lookback("sma", 20) == 20
    assert minimum_lookback("ema", 20) == 20
    assert minimum_lookback("rsi", 14) == 15
    assert minimum_lookback("atr", 14) == 15
    assert minimum_lookback("rolling_high", 10) == 10
    assert minimum_lookback("volume_ratio", 20) == 21
    assert minimum_lookback("return", 5) == 6
