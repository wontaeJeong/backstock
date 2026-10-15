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


@dataclass(frozen=True, slots=True)
class FilledExecution:
    fill: Fill


@dataclass(frozen=True, slots=True)
class PendingExecution:
    reason: str


ExecutionDecision = FilledExecution | PendingExecution


def execute_order(request: ExecutionRequest) -> ExecutionDecision:
    order = request.order
    bar = request.bar
    if bar.instrument_id != order.intent.instrument_id:
        return PendingExecution("different_instrument")
    execution_at = bar.timestamp - request.bar_duration
    if bar.timestamp <= order.intent.submitted_at or execution_at < order.intent.submitted_at:
        return PendingExecution("not_yet_eligible")
    reference_price = _reference_price(order, bar)
    if reference_price is None:
        return PendingExecution("limit_not_touched")
    execution_price = _slipped_price(order, reference_price, request.costs.slippage_bps)
    notional = execution_price * order.remaining_quantity
    commission = notional * request.costs.commission_rate
    tax = notional * request.costs.sell_tax_rate if order.intent.side is Side.SELL else Decimal(0)
    slippage = abs(execution_price - reference_price) * order.remaining_quantity
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
        )
    )


def _reference_price(order: Order, bar: Bar) -> Decimal | None:
    match order.intent.order_type:
        case OrderType.MARKET:
            return bar.open
        case OrderType.LIMIT:
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
