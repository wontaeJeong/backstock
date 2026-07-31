from datetime import UTC, datetime

import pytest

from packages.backtest.models import Order, OrderIntent, OrderState, OrderType, Side
from packages.backtest.orders import InvalidOrderTransitionError, transition_order


def _order() -> Order:
    return Order(
        order_id="order-000001",
        intent=OrderIntent(
            instrument_id="AAA",
            submitted_at=datetime(2024, 1, 2, tzinfo=UTC),
            side=Side.BUY,
            quantity=5,
            order_type=OrderType.MARKET,
            reason="golden entry",
        ),
    )


def test_order_transition_reaches_filled_terminal_state() -> None:
    order = _order()

    filled = transition_order(order, OrderState.FILLED, "filled at next open", filled_quantity=5)

    assert filled.state is OrderState.FILLED
    assert filled.filled_quantity == 5
    assert filled.remaining_quantity == 0


def test_terminal_order_rejects_later_transition() -> None:
    filled = transition_order(_order(), OrderState.FILLED, "filled", filled_quantity=5)

    with pytest.raises(InvalidOrderTransitionError):
        _ = transition_order(filled, OrderState.CANCELLED, "too late")
