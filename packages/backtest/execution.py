from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from packages.backtest.models import CostConfig, Fill, Order, OrderType, Side
from packages.domain.market_data import Bar

BASIS_POINTS = Decimal(10_000)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    order: Order
    bar: Bar
    costs: CostConfig
    fill_id: str
    bar_duration: timedelta = timedelta(0)
    spread_bps: Decimal = Decimal(0)
    latency_ms: int = 0
    volume_participation: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FilledExecution:
    fill: Fill


@dataclass(frozen=True, slots=True)
class PendingExecution:
    reason: str
    triggered: bool = False


ExecutionDecision = FilledExecution | PendingExecution


def execute_order(request: ExecutionRequest) -> ExecutionDecision:
    order = request.order
    bar = request.bar
    if bar.instrument_id != order.intent.instrument_id:
        return PendingExecution("different_instrument")
    execution_at = bar.timestamp - request.bar_duration
    earliest = order.intent.submitted_at + timedelta(milliseconds=request.latency_ms)
    if bar.timestamp <= order.intent.submitted_at or execution_at < earliest:
        return PendingExecution("not_yet_eligible")
    reference_price = _stop_reference(order, bar)
    if isinstance(reference_price, PendingExecution):
        return reference_price
    if (
        order.intent.order_type is OrderType.STOP
        and order.triggered_at is None
        and reference_price != bar.open
    ):
        # A range touch is known only at bar close, not at its open.
        execution_at = bar.timestamp
    triggered = order.intent.order_type in {OrderType.STOP, OrderType.STOP_LIMIT}
    if (
        request.volume_participation is not None
        and order.remaining_quantity > Decimal(bar.volume) * request.volume_participation
    ):
        return PendingExecution("volume_cap_all_or_none", triggered=triggered)
    reference_price, base_price = _spread_prices(order, bar, reference_price, request.spread_bps)
    execution_price = _slipped_price(order, base_price, request.costs.slippage_bps)
    limit = order.intent.limit_price
    if limit is not None and (
        (order.intent.side is Side.BUY and base_price > limit)
        or (order.intent.side is Side.SELL and base_price < limit)
    ):
        return PendingExecution("limit_not_touched", triggered=triggered)
    notional = execution_price * order.remaining_quantity
    commission = notional * request.costs.commission_rate
    tax = notional * request.costs.sell_tax_rate if order.intent.side is Side.SELL else Decimal(0)
    slippage = abs(execution_price - base_price) * order.remaining_quantity
    return FilledExecution(
        Fill(
            fill_id=request.fill_id,
            order_id=order.order_id,
            instrument_id=order.intent.instrument_id,
            timestamp=execution_at,
            side=order.intent.side,
            quantity=order.remaining_quantity,
            reference_price=reference_price,
            execution_price=execution_price,
            commission=commission,
            tax=tax,
            slippage=slippage,
            spread=abs(base_price - reference_price) * order.remaining_quantity,
        )
    )


def _reference_price(order: Order, bar: Bar) -> Decimal | None:
    match order.intent.order_type:
        case OrderType.MARKET | OrderType.STOP:
            return bar.open
        case OrderType.LIMIT | OrderType.STOP_LIMIT:
            limit = order.intent.limit_price
            if limit is None:
                return None
            match order.intent.side:
                case Side.BUY:
                    if bar.open <= limit:
                        return bar.open
                    return limit if bar.low <= limit else None
                case Side.SELL:
                    if bar.open >= limit:
                        return bar.open
                    return limit if bar.high >= limit else None


def _stop_reference(order: Order, bar: Bar) -> Decimal | PendingExecution:
    stop = order.intent.stop_price
    if stop is None or order.triggered_at is not None:
        return _reference_price(order, bar) or PendingExecution("limit_not_touched")
    buy = order.intent.side is Side.BUY
    gap = bar.open >= stop if buy else bar.open <= stop
    touched = bar.high >= stop if buy else bar.low <= stop
    if not touched:
        return PendingExecution("stop_not_triggered")
    if order.intent.order_type is OrderType.STOP:
        return bar.open if gap else stop
    if not gap:
        return PendingExecution("stop_limit_intrabar_ambiguous", triggered=True)
    return _reference_price(order, bar) or PendingExecution("limit_not_touched", triggered=True)


def _spread_prices(
    order: Order, bar: Bar, reference: Decimal, spread_bps: Decimal
) -> tuple[Decimal, Decimal]:
    if bar.bid is not None and bar.ask is not None:
        return (bar.bid + bar.ask) / 2, bar.ask if order.intent.side is Side.BUY else bar.bid
    sign = Decimal(1) if order.intent.side is Side.BUY else Decimal(-1)
    return reference, reference * (1 + sign * spread_bps / BASIS_POINTS / 2)


def _slipped_price(order: Order, reference: Decimal, slippage_bps: Decimal) -> Decimal:
    rate = slippage_bps / BASIS_POINTS
    match order.intent.side:
        case Side.BUY:
            slipped = reference * (Decimal(1) + rate)
            if order.intent.limit_price is not None:
                return min(slipped, order.intent.limit_price)
            return slipped
        case Side.SELL:
            slipped = reference * (Decimal(1) - rate)
            if order.intent.limit_price is not None:
                return max(slipped, order.intent.limit_price)
            return slipped
