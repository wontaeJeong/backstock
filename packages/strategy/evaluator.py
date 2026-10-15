"""Translate a validated StrategyDefinition into OrderIntent decisions."""

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Final, override

from packages.backtest.models import (
    OrderIntent,
    OrderType,
    PortfolioSnapshot,
    Position,
    Side,
    TimeInForce,
)
from packages.backtest.ports import EvaluationContext, StrategyEvaluator
from packages.domain.market_data import Bar
from packages.strategy.indicators import compute_indicator
from packages.strategy.schema import (
    AllCondition,
    AnyCondition,
    AtrRiskSizing,
    BarField,
    CalendarField,
    CompareCondition,
    Condition,
    ConstantValue,
    CrossCondition,
    FixedNotionalSizing,
    FixedQuantitySizing,
    IndicatorRef,
    NotCondition,
    OrderRule,
    PercentEquitySizing,
    PortfolioField,
    PositionField,
    PositionSizing,
    RiskRules,
    StopLossRule,
    StrategyDefinition,
    TakeProfitRule,
    TrailingStopRule,
    Value,
)
from packages.strategy.validation import create_strategy_version

_BASIS_POINTS: Final = Decimal(10_000)
_PERCENT: Final = Decimal(100)


@dataclass(frozen=True, slots=True)
class _PositionRuntime:
    entry_price: Decimal
    entry_bar_count: int
    peak_price: Decimal
    trough_price: Decimal


@dataclass(frozen=True, slots=True)
class _Evaluation:
    value: bool
    path: str
    detail: str
    available: bool = True


@dataclass(frozen=True, slots=True)
class _MarketState:
    portfolio: PortfolioSnapshot
    position: Position | None
    runtime: _PositionRuntime | None


@dataclass(frozen=True, slots=True)
class _Trace:
    strategy_version: str
    rule_path: str
    reason: str


class DslStrategyEvaluator(StrategyEvaluator):
    """Stateful evaluator: tracks per-instrument entry price/time/peak from portfolio deltas."""

    def __init__(self, definition: StrategyDefinition, version_id: str | None = None) -> None:
        """Bind an immutable definition and precompute its version id if not supplied."""
        self._definition = definition
        self._version_id = version_id or create_strategy_version(definition).version_id
        self._last_quantity: dict[str, int] = {}
        self._runtime: dict[str, _PositionRuntime] = {}

    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
        instrument_id = context.current_bar.instrument_id
        if instrument_id not in self._definition.universe:
            return ()
        history = tuple(bar for bar in context.history if bar.instrument_id == instrument_id)
        position = _find_position(context.portfolio, instrument_id)
        runtime = self._sync_position(context, position)
        state = _MarketState(portfolio=context.portfolio, position=position, runtime=runtime)
        if position is None or position.quantity == 0:
            return self._evaluate_entry(context, history, state)
        return self._evaluate_exit(context, history, position, state)

    def _sync_position(
        self, context: EvaluationContext, position: Position | None
    ) -> _PositionRuntime | None:
        instrument_id = context.current_bar.instrument_id
        previous_quantity = self._last_quantity.get(instrument_id, 0)
        if position is not None and position.quantity > 0:
            self._update_runtime(context, position, opened=previous_quantity == 0)
            self._last_quantity[instrument_id] = position.quantity
        else:
            self._runtime.pop(instrument_id, None)
            self._last_quantity[instrument_id] = 0
        return self._runtime.get(instrument_id)

    def _update_runtime(
        self, context: EvaluationContext, position: Position, *, opened: bool
    ) -> None:
        instrument_id = context.current_bar.instrument_id
        if opened:
            entry_bar_count = sum(
                1 for bar in context.history if bar.instrument_id == instrument_id
            )
            self._runtime[instrument_id] = _PositionRuntime(
                entry_price=position.average_cost,
                entry_bar_count=entry_bar_count,
                peak_price=context.current_bar.close,
                trough_price=context.current_bar.close,
            )
            return
        existing = self._runtime.get(instrument_id)
        if existing is not None:
            self._runtime[instrument_id] = replace(
                existing,
                peak_price=max(existing.peak_price, context.current_bar.high),
                trough_price=min(existing.trough_price, context.current_bar.low),
            )

    def _evaluate_entry(
        self, context: EvaluationContext, history: tuple[Bar, ...], state: _MarketState
    ) -> tuple[OrderIntent, ...]:
        result = _evaluate_condition(self._definition.entry.condition, history, state, "entry")
        if not result.available or not result.value:
            return ()
        quantity = _size_position(self._definition.position_sizing, context.portfolio, history)
        if quantity <= 0:
            return ()
        trace = _Trace(self._version_id, result.path, f"entry: {result.detail}")
        return (_build_order(context, Side.BUY, quantity, self._definition.order, trace),)

    def _evaluate_exit(
        self,
        context: EvaluationContext,
        history: tuple[Bar, ...],
        position: Position,
        state: _MarketState,
    ) -> tuple[OrderIntent, ...]:
        if state.runtime is not None:
            risk_reason = _risk_triggered(self._definition.risk, history, state.runtime)
            if risk_reason is not None:
                trace = _Trace(
                    self._version_id, f"risk/{risk_reason}", f"exit: {risk_reason} triggered"
                )
                order = _build_order(
                    context, Side.SELL, position.quantity, self._definition.order, trace
                )
                return (order,)
        condition = self._definition.exit.condition
        if condition is not None:
            result = _evaluate_condition(condition, history, state, "exit")
            if result.available and result.value:
                trace = _Trace(self._version_id, result.path, f"exit: {result.detail}")
                order = _build_order(
                    context, Side.SELL, position.quantity, self._definition.order, trace
                )
                return (order,)
        return ()


def _find_position(portfolio: PortfolioSnapshot, instrument_id: str) -> Position | None:
    return next((item for item in portfolio.positions if item.instrument_id == instrument_id), None)


def _evaluate_condition(
    condition: Condition, history: tuple[Bar, ...], state: _MarketState, path: str
) -> _Evaluation:
    match condition:
        case AllCondition(conditions=items):
            results = tuple(
                _evaluate_condition(item, history, state, f"{path}/all[{index}]")
                for index, item in enumerate(items)
            )
            return _Evaluation(
                all(result.value for result in results),
                path,
                " and ".join(result.detail for result in results),
                all(result.available for result in results),
            )
        case AnyCondition(conditions=items):
            results = tuple(
                _evaluate_condition(item, history, state, f"{path}/any[{index}]")
                for index, item in enumerate(items)
            )
            return _Evaluation(
                any(result.value for result in results),
                path,
                " or ".join(result.detail for result in results),
                all(result.available for result in results),
            )
        case NotCondition(condition=inner):
            result = _evaluate_condition(inner, history, state, f"{path}/not")
            return _Evaluation(not result.value, path, f"not({result.detail})", result.available)
        case CompareCondition(op=op, left=left, right=right):
            left_value = _resolve_value(left, history, state)
            right_value = _resolve_value(right, history, state)
            return _Evaluation(
                _compare(op, left_value, right_value),
                f"{path}/{op}",
                f"{op}(left={left_value}, right={right_value})",
                left_value is not None and right_value is not None,
            )
        case CrossCondition(op=op, left=left, right=right):
            previous_history = history[:-1]
            current_left = _resolve_value(left, history, state)
            current_right = _resolve_value(right, history, state)
            previous_left = _resolve_value(left, previous_history, state)
            previous_right = _resolve_value(right, previous_history, state)
            return _Evaluation(
                _crosses(op, current_left, current_right, previous_left, previous_right),
                f"{path}/{op}",
                f"{op}(prev={previous_left}/{previous_right}, cur={current_left}/{current_right})",
                all(
                    item is not None
                    for item in (current_left, current_right, previous_left, previous_right)
                ),
            )


def _compare(op: str, left: Decimal | None, right: Decimal | None) -> bool:
    if left is None or right is None:
        return False
    match op:
        case "gt":
            return left > right
        case "gte":
            return left >= right
        case "lt":
            return left < right
        case "lte":
            return left <= right
        case _:
            return left == right


def _crosses(
    op: str,
    current_left: Decimal | None,
    current_right: Decimal | None,
    previous_left: Decimal | None,
    previous_right: Decimal | None,
) -> bool:
    if (
        current_left is None
        or current_right is None
        or previous_left is None
        or previous_right is None
    ):
        return False
    if op == "crosses_above":
        return previous_left <= previous_right and current_left > current_right
    return previous_left >= previous_right and current_left < current_right


def _resolve_value(value: Value, window: tuple[Bar, ...], state: _MarketState) -> Decimal | None:
    if not window:
        return None
    result: Decimal | None
    match value:
        case ConstantValue(value=constant):
            result = constant
        case BarField() as field:
            result = _resolve_bar_field(field, window)
        case IndicatorRef() as indicator:
            result = _resolve_indicator(indicator, window)
        case PositionField() as field:
            result = _resolve_position_field(field, window, state.position, state.runtime)
        case PortfolioField(field=field_name):
            result = state.portfolio.cash if field_name == "cash" else state.portfolio.equity
        case CalendarField() as field:
            result = _resolve_calendar_field(field, window)
    return result


def _resolve_bar_field(field: BarField, window: tuple[Bar, ...]) -> Decimal | None:
    index = len(window) - 1 - field.shift
    if index < 0:
        return None
    bar = window[index]
    match field.field:
        case "open":
            return bar.open
        case "high":
            return bar.high
        case "low":
            return bar.low
        case "close":
            return bar.close
        case _:
            return Decimal(bar.volume)


def _resolve_indicator(ref: IndicatorRef, window: tuple[Bar, ...]) -> Decimal | None:
    end = len(window) - ref.shift
    if end < 0:
        return None
    return compute_indicator(ref.indicator, ref.period, window[:end])


def _resolve_position_field(
    field: PositionField,
    window: tuple[Bar, ...],
    position: Position | None,
    runtime: _PositionRuntime | None,
) -> Decimal | None:
    if position is None:
        return None
    if field.field == "quantity":
        return Decimal(position.quantity)
    if field.field == "average_cost":
        return position.average_cost
    return _resolve_runtime_field(field, window, runtime)


def _resolve_runtime_field(
    field: PositionField, window: tuple[Bar, ...], runtime: _PositionRuntime | None
) -> Decimal | None:
    if runtime is None:
        return None
    if field.field == "unrealized_pnl_percent":
        if runtime.entry_price == 0:
            return None
        return window[-1].close / runtime.entry_price - 1
    return Decimal(len(window) - runtime.entry_bar_count)


def _resolve_calendar_field(field: CalendarField, window: tuple[Bar, ...]) -> Decimal:
    timestamp = window[-1].timestamp
    if field.field == "day_of_week":
        return Decimal(timestamp.weekday())
    if field.field == "day_of_month":
        return Decimal(timestamp.day)
    return Decimal(timestamp.month)


def _risk_triggered(
    risk: RiskRules, history: tuple[Bar, ...], runtime: _PositionRuntime
) -> str | None:
    current_price = history[-1].close
    if risk.stop_loss is not None:
        threshold = _bound_threshold(risk.stop_loss, runtime, history, direction=-1)
        if threshold is not None and current_price <= threshold:
            return "stop_loss"
    if risk.take_profit is not None:
        threshold = _bound_threshold(risk.take_profit, runtime, history, direction=1)
        if threshold is not None and current_price >= threshold:
            return "take_profit"
    if risk.trailing_stop is not None:
        threshold = _trailing_threshold(risk.trailing_stop, runtime, history)
        if threshold is not None and current_price <= threshold:
            return "trailing_stop"
    if risk.max_holding_bars is not None:
        holding_bars = len(history) - runtime.entry_bar_count
        if holding_bars >= risk.max_holding_bars:
            return "max_holding_bars"
    return None


def _bound_threshold(
    rule: StopLossRule | TakeProfitRule,
    runtime: _PositionRuntime,
    history: tuple[Bar, ...],
    *,
    direction: int,
) -> Decimal | None:
    if rule.mode == "percent":
        return runtime.entry_price * (Decimal(1) + direction * rule.value / _PERCENT)
    atr_value = compute_indicator("atr", rule.atr_period, history)
    if atr_value is None:
        return None
    return runtime.entry_price + direction * atr_value * rule.value


def _trailing_threshold(
    rule: TrailingStopRule, runtime: _PositionRuntime, history: tuple[Bar, ...]
) -> Decimal | None:
    if rule.mode == "percent":
        return runtime.peak_price * (Decimal(1) - rule.value / _PERCENT)
    atr_value = compute_indicator("atr", rule.atr_period, history)
    if atr_value is None:
        return None
    return runtime.peak_price - atr_value * rule.value


def _size_position(
    sizing: PositionSizing, portfolio: PortfolioSnapshot, history: tuple[Bar, ...]
) -> int:
    reference_price = history[-1].close
    if reference_price <= 0:
        return 0
    match sizing:
        case FixedQuantitySizing(quantity=quantity):
            return quantity
        case FixedNotionalSizing(notional=notional):
            return int(notional // reference_price)
        case PercentEquitySizing(percent=percent):
            return int((portfolio.equity * percent) // reference_price)
        case AtrRiskSizing(
            risk_percent=risk_percent, atr_period=atr_period, atr_multiple=atr_multiple
        ):
            return _atr_risk_quantity(portfolio, history, risk_percent, atr_period, atr_multiple)


def _atr_risk_quantity(
    portfolio: PortfolioSnapshot,
    history: tuple[Bar, ...],
    risk_percent: Decimal,
    atr_period: int,
    atr_multiple: Decimal,
) -> int:
    atr_value = compute_indicator("atr", atr_period, history)
    if atr_value is None or atr_value <= 0:
        return 0
    per_share_risk = atr_value * atr_multiple
    if per_share_risk <= 0:
        return 0
    return int((portfolio.equity * risk_percent) // per_share_risk)


def _build_order(
    context: EvaluationContext,
    side: Side,
    quantity: int,
    order_rule: OrderRule,
    trace: _Trace,
) -> OrderIntent:
    reference_price = context.current_bar.close
    order_type = OrderType.MARKET if order_rule.order_type == "market" else OrderType.LIMIT
    limit_price: Decimal | None = None
    if order_rule.order_type == "limit" and order_rule.limit_offset_bps is not None:
        offset = order_rule.limit_offset_bps / _BASIS_POINTS
        sign = Decimal(1) if side is Side.BUY else Decimal(-1)
        limit_price = reference_price * (Decimal(1) + sign * offset)
    return OrderIntent(
        instrument_id=context.current_bar.instrument_id,
        submitted_at=context.current_bar.timestamp,
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        time_in_force=TimeInForce.DAY if order_rule.time_in_force == "day" else TimeInForce.GTC,
        reason=trace.reason,
        strategy_version=trace.strategy_version,
        rule_path=trace.rule_path,
    )
