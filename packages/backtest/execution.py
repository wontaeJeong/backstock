from dataclasses import dataclass
from datetime import datetime, timedelta
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
    triggered_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PendingExecution:
    reason: str
    triggered: bool = False
    triggered_at: datetime | None = None


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
    triggered_at = _trigger_time(request)
    reference_price = _stop_reference(order, bar, request.spread_bps, triggered_at)
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
        return PendingExecution(
            "volume_cap_all_or_none", triggered=triggered, triggered_at=triggered_at
        )
    reference_price, base_price = _spread_prices(order, bar, reference_price, request.spread_bps)
    execution_price = _slipped_price(order, base_price, request.costs.slippage_bps)
    limit = order.intent.limit_price
    if limit is not None and (
        (order.intent.side is Side.BUY and base_price > limit)
        or (order.intent.side is Side.SELL and base_price < limit)
    ):
        return PendingExecution("limit_not_touched", triggered=triggered, triggered_at=triggered_at)
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
        ),
        triggered_at=triggered_at,
    )


def _reference_price(order: Order, bar: Bar, spread_bps: Decimal) -> Decimal | None:
    match order.intent.order_type:
        case OrderType.MARKET | OrderType.STOP:
            return bar.open
        case OrderType.LIMIT | OrderType.STOP_LIMIT:
            limit = order.intent.limit_price
            if limit is None:
                return None
            buy = order.intent.side is Side.BUY
            if bar.bid is not None and bar.ask is not None:
                side_price = bar.ask if buy else bar.bid
                return bar.open if (side_price <= limit if buy else side_price >= limit) else None
            factor = 1 + (1 if buy else -1) * spread_bps / BASIS_POINTS / 2
            open_touched = bar.open * factor <= limit if buy else bar.open * factor >= limit
            if open_touched:
                return bar.open
            touched = bar.low * factor <= limit if buy else bar.high * factor >= limit
            return limit / factor if touched else None


def _trigger_time(request: ExecutionRequest) -> datetime | None:
    order, bar = request.order, request.bar
    stop = order.intent.stop_price
    if stop is None or order.triggered_at is not None:
        return None
    gap = bar.open >= stop if order.intent.side is Side.BUY else bar.open <= stop
    return bar.timestamp - request.bar_duration if gap else bar.timestamp


def _stop_reference(
    order: Order, bar: Bar, spread_bps: Decimal, triggered_at: datetime | None
) -> Decimal | PendingExecution:
    stop = order.intent.stop_price
    if stop is None or order.triggered_at is not None:
        return _reference_price(order, bar, spread_bps) or PendingExecution("limit_not_touched")
    buy = order.intent.side is Side.BUY
    gap = bar.open >= stop if buy else bar.open <= stop
    touched = bar.high >= stop if buy else bar.low <= stop
    if not touched:
        return PendingExecution("stop_not_triggered")
    if order.intent.order_type is OrderType.STOP:
        return bar.open if gap else stop
    if not gap:
        return PendingExecution(
            "stop_limit_intrabar_ambiguous", triggered=True, triggered_at=triggered_at
        )
    return _reference_price(order, bar, spread_bps) or PendingExecution(
        "limit_not_touched", triggered=True, triggered_at=triggered_at
    )


def _spread_prices(
    order: Order, bar: Bar, reference: Decimal, spread_bps: Decimal
) -> tuple[Decimal, Decimal]:
    if bar.bid is not None and bar.ask is not None:
        return (bar.bid + bar.ask) / 2, bar.ask if order.intent.side is Side.BUY else bar.bid
    sign = Decimal(1) if order.intent.side is Side.BUY else Decimal(-1)
    base = reference * (1 + sign * spread_bps / BASIS_POINTS / 2)
    if order.intent.limit_price is not None:
        # Range eligibility was checked on the executable side. At an intrabar
        # boundary use the exact limit, avoiding division/multiplication roundoff.
        limit = order.intent.limit_price
        base = min(base, limit) if order.intent.side is Side.BUY else max(base, limit)
    return reference, base


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
