from decimal import Decimal
from typing import Final

from packages.backtest.models import BacktestInput
from packages.backtest.results import (
    BacktestResult,
    BacktestSummary,
    BenchmarkPoint,
    ReproducibilityMetadata,
)
from packages.backtest.runtime import EngineState
from packages.domain.market_data import Bar

ENGINE_VERSION: Final = "backtest.v1"


def build_result(state: EngineState, backtest_input: BacktestInput) -> BacktestResult:
    timestamp = state.history[-1].timestamp if state.history else backtest_input.bars[0].timestamp
    final_snapshot = state.mark(timestamp)
    if not state.snapshots or state.snapshots[-1] != final_snapshot:
        state.snapshots.append(final_snapshot)
    summary = BacktestSummary(
        initial_cash=backtest_input.config.initial_cash,
        final_equity=final_snapshot.equity,
        total_return=final_snapshot.equity / backtest_input.config.initial_cash - Decimal(1),
        realized_pnl=final_snapshot.realized_pnl,
        unrealized_pnl=final_snapshot.unrealized_pnl,
        commission=state.portfolio.total_commission,
        tax=state.portfolio.total_tax,
        slippage=state.portfolio.total_slippage,
    )
    return BacktestResult(
        status=state.status,
        summary=summary,
        orders=tuple(state.orders),
        fills=tuple(state.fills),
        portfolio=tuple(state.snapshots),
        benchmark=_benchmark(backtest_input, state.history),
        events=tuple(state.events),
        metadata=ReproducibilityMetadata(
            snapshot=backtest_input.snapshot,
            strategy_version=backtest_input.strategy_version,
            code_revision=backtest_input.code_revision,
            engine_version=ENGINE_VERSION,
            seed=backtest_input.config.seed,
        ),
        failure_reason=state.failure_reason,
    )


def _benchmark(backtest_input: BacktestInput, history: list[Bar]) -> tuple[BenchmarkPoint, ...]:
    instrument_id = backtest_input.config.benchmark_instrument_id
    if instrument_id is None:
        return ()
    bars = tuple(bar for bar in history if bar.instrument_id == instrument_id)
    if not bars:
        return ()
    first_close = bars[0].close
    return tuple(
        BenchmarkPoint(
            timestamp=bar.timestamp,
            value=backtest_input.config.initial_cash * bar.close / first_close,
        )
        for bar in bars
    )
