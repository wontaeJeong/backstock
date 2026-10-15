from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from packages.backtest.events import EventKind
from packages.backtest.execution import (
    BASIS_POINTS,
    ExecutionRequest,
    FilledExecution,
    PendingExecution,
    execute_order,
)
from packages.backtest.ledger import (
    InsufficientCashError,
    InsufficientPositionError,
    apply_fill,
)
from packages.backtest.models import (
    BacktestConfig,
    CancelIntent,
    EndOrderPolicy,
    EndPositionPolicy,
    Fill,
    Order,
    OrderIntent,
    OrderState,
    OrderType,
    Side,
    TimeInForce,
)
from packages.backtest.orders import transition_order
from packages.backtest.runtime import EngineState, EventDetails
from packages.domain.market_data import Bar


def execute_orders(state: EngineState, bar: Bar, config: BacktestConfig) -> None:
    for index, order in enumerate(tuple(state.orders)):
        if order.state is not OrderState.ACCEPTED:
            continue
        if (
            config.bar_interval != "1d"
            and order.intent.time_in_force is TimeInForce.DAY
            and bar.instrument_id == order.intent.instrument_id
            and bar.timestamp.astimezone(ZoneInfo("America/New_York")).date()
            > order.intent.submitted_at.astimezone(ZoneInfo("America/New_York")).date()
        ):
            state.orders[index] = transition_order(order, OrderState.EXPIRED, "session ended")
            continue
        decision = execute_order(
            ExecutionRequest(
                order=order,
                bar=bar,
                costs=config.costs,
                fill_id=f"fill-{len(state.fills) + 1:06d}",
                bar_duration=timedelta(minutes={"1d": 0, "1m": 1, "5m": 5}[config.bar_interval]),
            )
        )
        match decision:
            case FilledExecution(fill=fill):
                _apply_execution(state, index, order, fill)
            case PendingExecution(reason="limit_not_touched"):
                if order.intent.time_in_force is TimeInForce.DAY and config.bar_interval == "1d":
                    expired = transition_order(order, OrderState.EXPIRED, "day order expired")
                    state.orders[index] = expired
                    state.record(
                        bar.timestamp,
                        EventKind.ORDER_EXPIRED,
                        expired.state_reason,
                        EventDetails(
                            instrument_id=order.intent.instrument_id,
                            order_id=order.order_id,
                        ),
                    )
            case PendingExecution():
                continue


def process_decisions(
    state: EngineState, bar: Bar, decisions: tuple[OrderIntent | CancelIntent, ...]
) -> None:
    for decision in decisions:
        match decision:
            case OrderIntent() as intent:
                _accept_intent(state, bar, intent)
            case CancelIntent() as cancellation:
                _cancel_order(state, bar, cancellation)


def finish_orders(state: EngineState, timestamp: datetime, config: BacktestConfig) -> None:
    for index, order in enumerate(tuple(state.orders)):
        if order.state is not OrderState.ACCEPTED:
            continue
        match config.end_order_policy:
            case EndOrderPolicy.EXPIRE:
                target = OrderState.EXPIRED
                kind = EventKind.ORDER_EXPIRED
            case EndOrderPolicy.CANCEL:
                target = OrderState.CANCELLED
                kind = EventKind.ORDER_CANCELLED
        final = transition_order(order, target, "end-of-data order policy")
        state.orders[index] = final
        state.record(
            timestamp,
            kind,
            final.state_reason,
            EventDetails(order_id=order.order_id),
        )


def finish_positions(state: EngineState, bars: tuple[Bar, ...], config: BacktestConfig) -> None:
    match config.end_position_policy:
        case EndPositionPolicy.MARK_TO_LAST_CLOSE:
            return
        case EndPositionPolicy.LIQUIDATE_AT_LAST_CLOSE:
            for position in tuple(state.portfolio.positions):
                bar = next(
                    item for item in reversed(bars) if item.instrument_id == position.instrument_id
                )
                order = Order(
                    order_id=f"order-{len(state.orders) + 1:06d}",
                    intent=OrderIntent(
                        instrument_id=position.instrument_id,
                        submitted_at=bar.timestamp,
                        side=Side.SELL,
                        quantity=position.quantity,
                        order_type=OrderType.MARKET,
                        reason="end-of-data liquidation",
                    ),
                )
                state.orders.append(order)
                state.record(
                    bar.timestamp,
                    EventKind.ORDER_ACCEPTED,
                    "end-of-data liquidation accepted",
                    EventDetails(instrument_id=position.instrument_id, order_id=order.order_id),
                )
                rate = config.costs.slippage_bps / BASIS_POINTS
                execution_price = bar.close * (Decimal(1) - rate)
                notional = execution_price * position.quantity
                fill = Fill(
                    fill_id=f"fill-{len(state.fills) + 1:06d}",
                    order_id=order.order_id,
                    instrument_id=position.instrument_id,
                    timestamp=bar.timestamp,
                    side=Side.SELL,
                    quantity=position.quantity,
                    reference_price=bar.close,
                    execution_price=execution_price,
                    commission=notional * config.costs.commission_rate,
                    tax=notional * config.costs.sell_tax_rate,
                    slippage=abs(execution_price - bar.close) * position.quantity,
                )
                _apply_execution(state, len(state.orders) - 1, order, fill)


def _apply_execution(state: EngineState, index: int, order: Order, fill: Fill) -> None:
    try:
        portfolio = apply_fill(state.portfolio, fill)
    except InsufficientCashError:
        _reject_order(state, index, order, fill.timestamp, "insufficient cash")
        return
    except InsufficientPositionError:
        _reject_order(state, index, order, fill.timestamp, "insufficient position")
        return
    state.portfolio = portfolio
    state.orders[index] = transition_order(
        order, OrderState.FILLED, "filled on eligible bar", filled_quantity=fill.quantity
    )
    state.fills.append(fill)
    state.record(
        fill.timestamp,
        EventKind.FILL,
        "order filled",
        EventDetails(
            instrument_id=fill.instrument_id,
            order_id=fill.order_id,
            quantity=fill.quantity,
            reference_price=fill.reference_price,
            execution_price=fill.execution_price,
            commission=fill.commission,
            tax=fill.tax,
            slippage=fill.slippage,
        ),
    )
    marked = state.mark(fill.timestamp)
    state.record(
        fill.timestamp,
        EventKind.LEDGER_UPDATE,
        "fill applied to ledger",
        EventDetails(cash=marked.cash, equity=marked.equity),
    )


def _accept_intent(state: EngineState, bar: Bar, intent: OrderIntent) -> None:
    order = Order(order_id=f"order-{len(state.orders) + 1:06d}", intent=intent)
    if any(
        existing.state is OrderState.ACCEPTED
        and existing.intent.instrument_id == intent.instrument_id
        for existing in state.orders
    ):
        _reject_order_for_pending(state, order, bar)
        return
    state.record(
        bar.timestamp,
        EventKind.SIGNAL,
        intent.reason,
        EventDetails(instrument_id=intent.instrument_id),
    )
    state.record(
        bar.timestamp,
        EventKind.ORDER_INTENT,
        "strategy emitted order intent",
        EventDetails(instrument_id=intent.instrument_id, order_id=order.order_id),
    )
    valid_time = intent.submitted_at == bar.timestamp
    valid_instrument = intent.instrument_id == bar.instrument_id
    valid_position = (
        intent.side is Side.BUY or state.held_quantity(intent.instrument_id) >= intent.quantity
    )
    state.record(
        bar.timestamp,
        EventKind.RISK_EVALUATION,
        "basic long-only feasibility evaluated",
        EventDetails(instrument_id=intent.instrument_id, order_id=order.order_id),
    )
    if not valid_time or not valid_instrument or not valid_position:
        rejected = transition_order(order, OrderState.REJECTED, "invalid long-only intent")
        state.orders.append(rejected)
        state.record(
            bar.timestamp,
            EventKind.ORDER_REJECTED,
            rejected.state_reason,
            EventDetails(instrument_id=intent.instrument_id, order_id=order.order_id),
        )
        return
    state.orders.append(order)
    state.record(
        bar.timestamp,
        EventKind.ORDER_ACCEPTED,
        "order accepted for a future bar",
        EventDetails(instrument_id=intent.instrument_id, order_id=order.order_id),
    )


def _reject_order_for_pending(state: EngineState, order: Order, bar: Bar) -> None:
    rejected = transition_order(order, OrderState.REJECTED, "pending order already exists")
    state.orders.append(rejected)
    state.record(
        bar.timestamp,
        EventKind.ORDER_REJECTED,
        rejected.state_reason,
        EventDetails(instrument_id=order.intent.instrument_id, order_id=order.order_id),
    )


def _cancel_order(state: EngineState, bar: Bar, cancellation: CancelIntent) -> None:
    if cancellation.submitted_at != bar.timestamp:
        state.record(
            bar.timestamp,
            EventKind.ORDER_CANCEL_REJECTED,
            "cancel intent timestamp does not match current bar",
            EventDetails(order_id=cancellation.order_id),
        )
        return
    for index, order in enumerate(state.orders):
        if order.order_id == cancellation.order_id and order.state is OrderState.ACCEPTED:
            cancelled = transition_order(order, OrderState.CANCELLED, cancellation.reason)
            state.orders[index] = cancelled
            state.record(
                cancellation.submitted_at,
                EventKind.ORDER_CANCELLED,
                cancellation.reason,
                EventDetails(order_id=order.order_id),
            )
            return


def _reject_order(
    state: EngineState, index: int, order: Order, timestamp: datetime, reason: str
) -> None:
    state.orders[index] = transition_order(order, OrderState.REJECTED, reason)
    state.record(
        timestamp,
        EventKind.ORDER_REJECTED,
        reason,
        EventDetails(instrument_id=order.intent.instrument_id, order_id=order.order_id),
    )
