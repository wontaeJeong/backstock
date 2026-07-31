from typing import Final

from packages.backtest.models import Order, OrderState

TERMINAL_ORDER_STATES: Final = frozenset(
    {OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED, OrderState.REJECTED}
)


class InvalidOrderTransitionError(Exception):
    current: OrderState
    target: OrderState

    def __init__(self, current: OrderState, target: OrderState) -> None:
        """Preserve both states for structured engine failure handling."""
        self.current = current
        self.target = target
        super().__init__(f"cannot transition order from {current} to {target}")


def transition_order(
    order: Order,
    target: OrderState,
    reason: str,
    *,
    filled_quantity: int | None = None,
) -> Order:
    if order.state in TERMINAL_ORDER_STATES or target is OrderState.ACCEPTED:
        raise InvalidOrderTransitionError(order.state, target)
    quantity = order.filled_quantity if filled_quantity is None else filled_quantity
    if target is OrderState.FILLED and quantity != order.intent.quantity:
        raise InvalidOrderTransitionError(order.state, target)
    if target is not OrderState.FILLED and quantity != order.filled_quantity:
        raise InvalidOrderTransitionError(order.state, target)
    return order.model_copy(
        update={"state": target, "filled_quantity": quantity, "state_reason": reason}
    )
