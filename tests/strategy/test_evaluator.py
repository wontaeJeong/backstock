from datetime import UTC, datetime
from decimal import Decimal

from packages.backtest.engine import BacktestEngine
from packages.backtest.models import (
    BacktestConfig,
    BacktestInput,
    CostConfig,
    PortfolioSnapshot,
    Position,
    Side,
    SnapshotReference,
)
from packages.backtest.ports import EvaluationContext
from packages.domain.market_data import AdjustmentMode, Bar
from packages.strategy.evaluator import DslStrategyEvaluator
from packages.strategy.schema import (
    AtrRiskSizing,
    CompareCondition,
    ConstantValue,
    CrossCondition,
    EntryRule,
    ExitRule,
    FixedNotionalSizing,
    FixedQuantitySizing,
    IndicatorRef,
    PercentEquitySizing,
    RiskRules,
    StopLossRule,
    StrategyDefinition,
    TakeProfitRule,
    TrailingStopRule,
)

_ALWAYS_TRUE = CompareCondition(
    op="gt", left=ConstantValue(value=Decimal(1)), right=ConstantValue(value=Decimal(0))
)
_ALWAYS_FALSE = CompareCondition(
    op="lt", left=ConstantValue(value=Decimal(1)), right=ConstantValue(value=Decimal(0))
)


def _bar(day: int, *, high: str, low: str, close: str) -> Bar:
    return Bar(
        instrument_id="AAA",
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1000,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


def _flat_bar(day: int, value: str) -> Bar:
    return _bar(day, high=value, low=value, close=value)


def _flat_portfolio(
    timestamp: datetime, *, cash: Decimal, equity: Decimal, positions: tuple[Position, ...] = ()
) -> PortfolioSnapshot:
    market_value = equity - cash
    return PortfolioSnapshot(
        timestamp=timestamp,
        cash=cash,
        market_value=market_value,
        equity=equity,
        realized_pnl=Decimal(0),
        unrealized_pnl=Decimal(0),
        positions=positions,
    )


def _backtest_input(bars: tuple[Bar, ...], config: BacktestConfig) -> BacktestInput:
    return BacktestInput(
        snapshot=SnapshotReference(
            snapshot_id="a" * 64,
            normalized_checksum=f"sha256:{'b' * 64}",
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        bars=bars,
        config=config,
        strategy_version="strategy-v1",
        code_revision="test-revision",
    )


def test_entry_is_skipped_during_indicator_warmup() -> None:
    definition = StrategyDefinition(
        name="warmup",
        universe=("AAA",),
        entry=EntryRule(
            condition=CompareCondition(
                op="gt",
                left=IndicatorRef(indicator="sma", period=5),
                right=ConstantValue(value=Decimal(0)),
            )
        ),
        position_sizing=FixedQuantitySizing(quantity=1),
    )
    evaluator = DslStrategyEvaluator(definition)
    bar = _flat_bar(1, "100")

    decisions = evaluator.evaluate(
        EvaluationContext(
            current_bar=bar,
            history=(bar,),
            portfolio=_flat_portfolio(bar.timestamp, cash=Decimal(10000), equity=Decimal(10000)),
        )
    )

    assert decisions == ()


def test_moving_average_crossover_enters_and_exits_via_the_engine() -> None:
    closes = ("10", "10", "10", "10", "20", "30", "30", "30", "10", "10", "10")
    bars = tuple(_flat_bar(day, value) for day, value in enumerate(closes, start=1))
    definition = StrategyDefinition(
        name="fast-slow-cross",
        universe=("AAA",),
        entry=EntryRule(
            condition=CrossCondition(
                op="crosses_above",
                left=IndicatorRef(indicator="sma", period=2),
                right=IndicatorRef(indicator="sma", period=3),
            )
        ),
        exit=ExitRule(
            condition=CrossCondition(
                op="crosses_below",
                left=IndicatorRef(indicator="sma", period=2),
                right=IndicatorRef(indicator="sma", period=3),
            )
        ),
        position_sizing=FixedQuantitySizing(quantity=5),
    )
    evaluator = DslStrategyEvaluator(definition)

    result = BacktestEngine().run(
        _backtest_input(bars, BacktestConfig(initial_cash=Decimal(100_000))), evaluator
    )

    assert [fill.side for fill in result.fills] == [Side.BUY, Side.SELL]
    # entry signal evaluated at bar index 4 (day 5) fills at the next bar's open
    assert result.fills[0].timestamp == bars[5].timestamp
    # exit signal evaluated at bar index 8 (day 9) fills at the next bar's open
    assert result.fills[1].timestamp == bars[9].timestamp
    entry_order = result.orders[0]
    assert entry_order.intent.rule_path == "entry/crosses_above"
    assert entry_order.intent.reason.startswith("entry:")


def test_fixed_notional_sizing_rounds_down_to_whole_shares() -> None:
    definition = StrategyDefinition(
        name="notional-sizing",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_TRUE),
        position_sizing=FixedNotionalSizing(notional=Decimal(1000)),
    )
    evaluator = DslStrategyEvaluator(definition)
    bar = _flat_bar(1, "100")

    decisions = evaluator.evaluate(
        EvaluationContext(
            current_bar=bar,
            history=(bar,),
            portfolio=_flat_portfolio(
                bar.timestamp, cash=Decimal(100_000), equity=Decimal(100_000)
            ),
        )
    )

    assert len(decisions) == 1
    assert decisions[0].quantity == 10


def test_notional_sizing_below_one_share_produces_no_order() -> None:
    definition = StrategyDefinition(
        name="too-small",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_TRUE),
        position_sizing=FixedNotionalSizing(notional=Decimal(50)),
    )
    evaluator = DslStrategyEvaluator(definition)
    bar = _flat_bar(1, "100")

    decisions = evaluator.evaluate(
        EvaluationContext(
            current_bar=bar,
            history=(bar,),
            portfolio=_flat_portfolio(
                bar.timestamp, cash=Decimal(100_000), equity=Decimal(100_000)
            ),
        )
    )

    assert decisions == ()


def test_percent_equity_sizing_uses_current_equity() -> None:
    definition = StrategyDefinition(
        name="percent-equity",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_TRUE),
        position_sizing=PercentEquitySizing(percent=Decimal("0.5")),
    )
    evaluator = DslStrategyEvaluator(definition)
    bar = _flat_bar(1, "100")

    decisions = evaluator.evaluate(
        EvaluationContext(
            current_bar=bar,
            history=(bar,),
            portfolio=_flat_portfolio(bar.timestamp, cash=Decimal(10_000), equity=Decimal(10_000)),
        )
    )

    assert len(decisions) == 1
    assert decisions[0].quantity == 50


def test_atr_risk_sizing_divides_risk_budget_by_per_share_risk() -> None:
    bars = (
        _bar(1, high="10", low="8", close="9"),
        _bar(2, high="12", low="9", close="11"),
        _bar(3, high="11", low="7", close="10"),
    )
    definition = StrategyDefinition(
        name="atr-risk",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_TRUE),
        position_sizing=AtrRiskSizing(
            risk_percent=Decimal("0.02"), atr_period=2, atr_multiple=Decimal(2)
        ),
    )
    evaluator = DslStrategyEvaluator(definition)

    decisions = evaluator.evaluate(
        EvaluationContext(
            current_bar=bars[-1],
            history=bars,
            portfolio=_flat_portfolio(
                bars[-1].timestamp, cash=Decimal(100_000), equity=Decimal(100_000)
            ),
        )
    )

    # ATR(2) at 3 bars = 3.5; per-share risk = 3.5 * 2 = 7; risk budget = 100000 * 0.02 = 2000
    # quantity = floor(2000 / 7) = 285
    assert len(decisions) == 1
    assert decisions[0].quantity == 285


def test_percent_stop_loss_triggers_an_exit() -> None:
    definition = StrategyDefinition(
        name="stop-loss",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_FALSE),
        position_sizing=FixedQuantitySizing(quantity=1),
        risk=RiskRules(stop_loss=StopLossRule(mode="percent", value=Decimal(10))),
    )
    evaluator = DslStrategyEvaluator(definition)
    entry_bar = _flat_bar(1, "100")
    position = Position(instrument_id="AAA", quantity=1, average_cost=Decimal(100))

    first = evaluator.evaluate(
        EvaluationContext(
            current_bar=entry_bar,
            history=(entry_bar,),
            portfolio=_flat_portfolio(
                entry_bar.timestamp,
                cash=Decimal(9900),
                equity=Decimal(10000),
                positions=(position,),
            ),
        )
    )
    assert first == ()

    drop_bar = _flat_bar(2, "85")
    second = evaluator.evaluate(
        EvaluationContext(
            current_bar=drop_bar,
            history=(entry_bar, drop_bar),
            portfolio=_flat_portfolio(
                drop_bar.timestamp, cash=Decimal(9900), equity=Decimal(9985), positions=(position,)
            ),
        )
    )

    assert len(second) == 1
    assert second[0].side is Side.SELL
    assert second[0].rule_path == "risk/stop_loss"


def test_take_profit_triggers_an_exit() -> None:
    definition = StrategyDefinition(
        name="take-profit",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_FALSE),
        position_sizing=FixedQuantitySizing(quantity=1),
        risk=RiskRules(take_profit=TakeProfitRule(mode="percent", value=Decimal(10))),
    )
    evaluator = DslStrategyEvaluator(definition)
    entry_bar = _flat_bar(1, "100")
    position = Position(instrument_id="AAA", quantity=1, average_cost=Decimal(100))
    evaluator.evaluate(
        EvaluationContext(
            current_bar=entry_bar,
            history=(entry_bar,),
            portfolio=_flat_portfolio(
                entry_bar.timestamp,
                cash=Decimal(9900),
                equity=Decimal(10000),
                positions=(position,),
            ),
        )
    )

    rise_bar = _flat_bar(2, "115")
    decisions = evaluator.evaluate(
        EvaluationContext(
            current_bar=rise_bar,
            history=(entry_bar, rise_bar),
            portfolio=_flat_portfolio(
                rise_bar.timestamp, cash=Decimal(9900), equity=Decimal(10015), positions=(position,)
            ),
        )
    )

    assert len(decisions) == 1
    assert decisions[0].rule_path == "risk/take_profit"


def test_trailing_stop_tracks_the_peak_since_entry() -> None:
    definition = StrategyDefinition(
        name="trailing-stop",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_FALSE),
        position_sizing=FixedQuantitySizing(quantity=1),
        risk=RiskRules(trailing_stop=TrailingStopRule(mode="percent", value=Decimal(10))),
    )
    evaluator = DslStrategyEvaluator(definition)
    position = Position(instrument_id="AAA", quantity=1, average_cost=Decimal(100))
    entry_bar = _flat_bar(1, "100")
    evaluator.evaluate(
        EvaluationContext(
            current_bar=entry_bar,
            history=(entry_bar,),
            portfolio=_flat_portfolio(
                entry_bar.timestamp,
                cash=Decimal(9900),
                equity=Decimal(10000),
                positions=(position,),
            ),
        )
    )
    peak_bar = _flat_bar(2, "120")
    unchanged = evaluator.evaluate(
        EvaluationContext(
            current_bar=peak_bar,
            history=(entry_bar, peak_bar),
            portfolio=_flat_portfolio(
                peak_bar.timestamp, cash=Decimal(9900), equity=Decimal(10020), positions=(position,)
            ),
        )
    )
    assert unchanged == ()

    pullback_bar = _flat_bar(3, "105")
    triggered = evaluator.evaluate(
        EvaluationContext(
            current_bar=pullback_bar,
            history=(entry_bar, peak_bar, pullback_bar),
            portfolio=_flat_portfolio(
                pullback_bar.timestamp,
                cash=Decimal(9900),
                equity=Decimal(10005),
                positions=(position,),
            ),
        )
    )

    # peak=120, trailing threshold = 120 * 0.9 = 108; price 105 <= 108 triggers the exit
    assert len(triggered) == 1
    assert triggered[0].rule_path == "risk/trailing_stop"


def test_max_holding_bars_forces_an_exit() -> None:
    definition = StrategyDefinition(
        name="max-holding",
        universe=("AAA",),
        entry=EntryRule(condition=_ALWAYS_FALSE),
        position_sizing=FixedQuantitySizing(quantity=1),
        risk=RiskRules(max_holding_bars=2),
    )
    evaluator = DslStrategyEvaluator(definition)
    position = Position(instrument_id="AAA", quantity=1, average_cost=Decimal(100))
    bars = tuple(_flat_bar(day, "100") for day in (1, 2, 3))

    for index in range(2):
        decisions = evaluator.evaluate(
            EvaluationContext(
                current_bar=bars[index],
                history=bars[: index + 1],
                portfolio=_flat_portfolio(
                    bars[index].timestamp,
                    cash=Decimal(9900),
                    equity=Decimal(10000),
                    positions=(position,),
                ),
            )
        )
        assert decisions == ()

    triggered = evaluator.evaluate(
        EvaluationContext(
            current_bar=bars[2],
            history=bars,
            portfolio=_flat_portfolio(
                bars[2].timestamp, cash=Decimal(9900), equity=Decimal(10000), positions=(position,)
            ),
        )
    )

    assert len(triggered) == 1
    assert triggered[0].rule_path == "risk/max_holding_bars"


def test_costs_are_applied_through_the_full_engine_round_trip() -> None:
    closes = ("10", "10", "10", "10", "20", "30", "30", "30", "10", "10", "10")
    bars = tuple(_flat_bar(day, value) for day, value in enumerate(closes, start=1))
    definition = StrategyDefinition(
        name="fast-slow-cross",
        universe=("AAA",),
        entry=EntryRule(
            condition=CrossCondition(
                op="crosses_above",
                left=IndicatorRef(indicator="sma", period=2),
                right=IndicatorRef(indicator="sma", period=3),
            )
        ),
        exit=ExitRule(
            condition=CrossCondition(
                op="crosses_below",
                left=IndicatorRef(indicator="sma", period=2),
                right=IndicatorRef(indicator="sma", period=3),
            )
        ),
        position_sizing=FixedQuantitySizing(quantity=5),
    )
    evaluator = DslStrategyEvaluator(definition)
    costs = CostConfig(commission_rate=Decimal("0.01"))

    result = BacktestEngine().run(
        _backtest_input(bars, BacktestConfig(initial_cash=Decimal(100_000), costs=costs)),
        evaluator,
    )

    assert result.summary.commission > 0
