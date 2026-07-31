from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.backtest.models import BacktestConfig, BacktestInput, CostConfig, SnapshotReference
from packages.domain.market_data import AdjustmentMode, Bar


def _bar() -> Bar:
    return Bar(
        instrument_id="AAA",
        timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        open=Decimal(100),
        high=Decimal(101),
        low=Decimal(99),
        close=Decimal(100),
        volume=1000,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


def _input(*bars: Bar, price_adjustment: AdjustmentMode = AdjustmentMode.RAW) -> BacktestInput:
    return BacktestInput(
        snapshot=SnapshotReference(
            snapshot_id="a" * 64,
            normalized_checksum=f"sha256:{'b' * 64}",
            price_adjustment=price_adjustment,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        bars=bars,
        config=BacktestConfig(initial_cash=Decimal(1000)),
        strategy_version="strategy-v1",
        code_revision="test-revision",
    )


def test_input_rejects_bars_with_snapshot_adjustment_mismatch() -> None:
    with pytest.raises(ValidationError, match="bar adjustments do not match"):
        _ = _input(_bar(), price_adjustment=AdjustmentMode.TOTAL_RETURN_ADJUSTED)


def test_input_rejects_duplicate_instrument_timestamp() -> None:
    bar = _bar()

    with pytest.raises(ValidationError, match="duplicate instrument timestamps"):
        _ = _input(bar, bar)


def test_cost_config_rejects_slippage_that_eliminates_sell_price() -> None:
    assert CostConfig(slippage_bps=Decimal(9999)).slippage_bps == Decimal(9999)

    with pytest.raises(ValidationError):
        _ = CostConfig(slippage_bps=Decimal(10_000))


def test_cost_config_rejects_sell_deductions_above_proceeds() -> None:
    valid = CostConfig(commission_rate=Decimal("0.6"), sell_tax_rate=Decimal("0.4"))
    assert valid.commission_rate + valid.sell_tax_rate == Decimal(1)

    with pytest.raises(ValidationError, match="sell commission and tax cannot exceed proceeds"):
        _ = CostConfig(commission_rate=Decimal("0.6"), sell_tax_rate=Decimal("0.4001"))
