from datetime import UTC, datetime
from decimal import Decimal

from packages.backtest.execution import (
    ExecutionRequest,
    FilledExecution,
    PendingExecution,
    execute_order,
)
from packages.backtest.models import CostConfig, Order, OrderIntent, OrderType, Side
from packages.domain.market_data import AdjustmentMode, Bar


def _bar(day: int, *, open_: str, high: str, low: str, close: str) -> Bar:
    return Bar(
        instrument_id="AAA",
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1000,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


def _order(
    side: Side,
    order_type: OrderType,
    *,
    quantity: int = 5,
    limit_price: str | None = None,
) -> Order:
    return Order(
        order_id="order-000001",
        intent=OrderIntent(
            instrument_id="AAA",
            submitted_at=datetime(2024, 1, 2, tzinfo=UTC),
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=None if limit_price is None else Decimal(limit_price),
            reason="fixture",
        ),
    )


def test_market_order_waits_for_next_bar_and_applies_adverse_slippage() -> None:
    order = _order(Side.BUY, OrderType.MARKET)
    costs = CostConfig(commission_rate=Decimal("0.01"), slippage_bps=Decimal(10))

    same_bar = execute_order(
        ExecutionRequest(
            order=order,
            bar=_bar(2, open_="100", high="101", low="99", close="100"),
            costs=costs,
            fill_id="fill-000001",
        )
    )
    next_bar = execute_order(
        ExecutionRequest(
            order=order,
            bar=_bar(3, open_="100", high="101", low="99", close="100"),
            costs=costs,
            fill_id="fill-000001",
        )
    )

    assert isinstance(same_bar, PendingExecution)
    assert isinstance(next_bar, FilledExecution)
    assert next_bar.fill.reference_price == Decimal(100)
    assert next_bar.fill.execution_price == Decimal("100.100")
    assert next_bar.fill.commission == Decimal("5.00500")
    assert next_bar.fill.slippage == Decimal("0.500")


def test_buy_limit_gap_fills_at_better_open_price() -> None:
    decision = execute_order(
        ExecutionRequest(
            order=_order(Side.BUY, OrderType.LIMIT, limit_price="95"),
            bar=_bar(3, open_="90", high="94", low="88", close="92"),
            costs=CostConfig(),
            fill_id="fill-000001",
        )
    )

    assert isinstance(decision, FilledExecution)
    assert decision.fill.execution_price == Decimal(90)


def test_limit_order_remains_pending_when_bar_does_not_touch() -> None:
    decision = execute_order(
        ExecutionRequest(
            order=_order(Side.BUY, OrderType.LIMIT, limit_price="95"),
            bar=_bar(3, open_="100", high="105", low="96", close="102"),
            costs=CostConfig(),
            fill_id="fill-000001",
        )
    )

    assert isinstance(decision, PendingExecution)
    assert decision.reason == "limit_not_touched"


def test_sell_fill_applies_tax_and_downward_slippage() -> None:
    decision = execute_order(
        ExecutionRequest(
            order=_order(Side.SELL, OrderType.MARKET),
            bar=_bar(3, open_="110", high="111", low="109", close="110"),
            costs=CostConfig(
                commission_rate=Decimal("0.01"),
                sell_tax_rate=Decimal("0.005"),
                slippage_bps=Decimal(10),
            ),
            fill_id="fill-000001",
        ),
    )

    assert isinstance(decision, FilledExecution)
    assert decision.fill.execution_price == Decimal("109.890")
    assert decision.fill.commission == Decimal("5.49450")
    assert decision.fill.tax == Decimal("2.747250")
    assert decision.fill.slippage == Decimal("0.550")
