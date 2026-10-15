from packages.backtest.events import EventKind
from packages.backtest.models import BacktestInput, OrderState, PortfolioState, RunStatus
from packages.backtest.ports import (
    CancellationProbe,
    EvaluationContext,
    StrategyEvaluationError,
    StrategyEvaluator,
)
from packages.backtest.processing import (
    execute_orders,
    finish_orders,
    finish_positions,
    process_decisions,
)
from packages.backtest.reporting import build_result
from packages.backtest.results import BacktestResult
from packages.backtest.runtime import EngineState, EventDetails


class BacktestEngine:
    def run(
        self,
        backtest_input: BacktestInput,
        strategy: StrategyEvaluator,
        cancellation: CancellationProbe | None = None,
    ) -> BacktestResult:
        state = EngineState(portfolio=PortfolioState(cash=backtest_input.config.initial_cash))
        ordered_bars = tuple(
            sorted(backtest_input.bars, key=lambda bar: (bar.timestamp, bar.instrument_id))
        )
        for bar in ordered_bars:
            if cancellation is not None and cancellation.should_cancel(len(state.events)):
                state.status = RunStatus.CANCELLED
                state.record(bar.timestamp, EventKind.RUN_CANCELLED, "cancellation requested")
                break
            state.record(bar.timestamp, EventKind.CLOCK, "daily clock advanced")
            state.marks[bar.instrument_id] = bar.open
            state.record(
                bar.timestamp,
                EventKind.MARKET,
                "daily bar became available",
                EventDetails(instrument_id=bar.instrument_id, reference_price=bar.close),
            )
            execute_orders(state, bar, backtest_input.config)
            state.history.append(bar)
            state.marks[bar.instrument_id] = bar.close
            snapshot = state.mark(bar.timestamp)
            state.record(
                bar.timestamp,
                EventKind.STRATEGY_EVALUATION,
                "strategy evaluated at close",
                EventDetails(instrument_id=bar.instrument_id),
            )
            try:
                decisions = strategy.evaluate(
                    EvaluationContext(
                        current_bar=bar,
                        history=tuple(state.history),
                        portfolio=snapshot,
                        pending_orders=tuple(
                            order for order in state.orders if order.state is OrderState.ACCEPTED
                        ),
                    )
                )
            except StrategyEvaluationError as error:
                state.status = RunStatus.FAILED
                state.failure_reason = error.reason
                state.record(bar.timestamp, EventKind.RUN_FAILED, error.reason)
                break
            process_decisions(state, bar, decisions)
            state.snapshots.append(snapshot)
            state.record(
                bar.timestamp,
                EventKind.METRICS_UPDATE,
                "portfolio marked at close",
                EventDetails(cash=snapshot.cash, equity=snapshot.equity),
            )
        if state.status is RunStatus.SUCCEEDED:
            finish_orders(state, ordered_bars[-1].timestamp, backtest_input.config)
            finish_positions(state, ordered_bars, backtest_input.config)
        return build_result(state, backtest_input)
