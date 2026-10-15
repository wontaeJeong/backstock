"""Reference strategy templates covering the four documented DSL patterns."""

from decimal import Decimal
from typing import Final

from packages.strategy.schema import (
    AllCondition,
    AtrRiskSizing,
    BarField,
    CalendarField,
    CompareCondition,
    ConstantValue,
    CrossCondition,
    EntryRule,
    ExitRule,
    IndicatorRef,
    OrderRule,
    PercentEquitySizing,
    RiskRules,
    StopLossRule,
    StrategyDefinition,
    TrailingStopRule,
)


def moving_average_crossover(universe: tuple[str, ...]) -> StrategyDefinition:
    fast = IndicatorRef(indicator="sma", period=20)
    slow = IndicatorRef(indicator="sma", period=60)
    return StrategyDefinition(
        name="moving-average-crossover",
        universe=universe,
        entry=EntryRule(condition=CrossCondition(op="crosses_above", left=fast, right=slow)),
        exit=ExitRule(condition=CrossCondition(op="crosses_below", left=fast, right=slow)),
        position_sizing=PercentEquitySizing(percent=Decimal("0.20")),
        order=OrderRule(order_type="market"),
    )


def mean_reversion(universe: tuple[str, ...]) -> StrategyDefinition:
    rsi = IndicatorRef(indicator="rsi", period=14)
    return StrategyDefinition(
        name="mean-reversion-rsi",
        universe=universe,
        entry=EntryRule(condition=CompareCondition(op="lt", left=rsi, right=_constant("30"))),
        exit=ExitRule(condition=CompareCondition(op="gt", left=rsi, right=_constant("55"))),
        position_sizing=PercentEquitySizing(percent=Decimal("0.15")),
        risk=RiskRules(stop_loss=StopLossRule(mode="percent", value=Decimal(8))),
        order=OrderRule(order_type="market"),
    )


def volatility_breakout(universe: tuple[str, ...]) -> StrategyDefinition:
    breakout_level = IndicatorRef(indicator="rolling_high", period=20, shift=1)
    return StrategyDefinition(
        name="volatility-breakout",
        universe=universe,
        entry=EntryRule(
            condition=AllCondition(
                conditions=(
                    CrossCondition(
                        op="crosses_above", left=BarField(field="close"), right=breakout_level
                    ),
                    CompareCondition(
                        op="gt",
                        left=IndicatorRef(indicator="volume_ratio", period=20),
                        right=_constant("1.5"),
                    ),
                )
            )
        ),
        exit=ExitRule(),
        position_sizing=AtrRiskSizing(
            risk_percent=Decimal("0.01"), atr_period=14, atr_multiple=Decimal(2)
        ),
        risk=RiskRules(
            stop_loss=StopLossRule(mode="atr_multiple", value=Decimal(2), atr_period=14),
            trailing_stop=TrailingStopRule(mode="atr_multiple", value=Decimal(3), atr_period=14),
        ),
        order=OrderRule(order_type="market"),
    )


def calendar_rebalancing(universe: tuple[str, ...]) -> StrategyDefinition:
    return StrategyDefinition(
        name="calendar-rebalancing",
        universe=universe,
        entry=EntryRule(
            condition=CompareCondition(
                op="lte", left=CalendarField(field="day_of_month"), right=_constant("5")
            )
        ),
        exit=ExitRule(),
        position_sizing=PercentEquitySizing(percent=Decimal("0.50")),
        risk=RiskRules(max_holding_bars=20),
        order=OrderRule(order_type="market"),
    )


def _constant(value: str) -> ConstantValue:
    return ConstantValue(value=Decimal(value))


TEMPLATES: Final = {
    "moving_average_crossover": moving_average_crossover,
    "mean_reversion": mean_reversion,
    "volatility_breakout": volatility_breakout,
    "calendar_rebalancing": calendar_rebalancing,
}
