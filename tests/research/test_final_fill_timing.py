from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from packages.application.research_analysis import export_csv, round_trips
from packages.application.simulations import SimulationService
from packages.backtest.engine import BacktestEngine
from packages.backtest.execution import ExecutionRequest, FilledExecution, execute_order
from packages.backtest.models import BacktestConfig, CostConfig, OrderIntent
from packages.backtest.ports import EvaluationContext
from tests.backtest.test_engine_golden import _input
from tests.research.test_execution_features import NOW, event, order
from tests.research.test_features import request


@pytest.mark.parametrize("minutes", [1, 5])
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("state", ["limit", "gap", "triggered"])
@pytest.mark.parametrize("at_open", [False, True])
@pytest.mark.parametrize("spread", [0, 10])
def test_limit_fill_time_distinguishes_open_from_later_touch(
    minutes: int, side: str, state: str, *, at_open: bool, spread: int
) -> None:
    buy = side == "buy"
    limit = "115" if buy else "85"
    price = ("112" if buy else "88") if at_open else ("120" if buy else "80")
    pending = order(
        side=side,
        order_type="limit" if state == "limit" else "stop_limit",
        limit_price=limit,
        time_in_force="gtc",
        **({"stop_price": "110" if buy else "90"} if state != "limit" else {}),
    )
    if state == "triggered":
        pending = pending.model_copy(update={"triggered_at": NOW})
    close = NOW + timedelta(minutes=minutes * 2)
    decision = execute_order(
        ExecutionRequest(
            pending,
            event(price=price, high="125", low="75", close="121", timestamp=close),
            CostConfig(slippage_bps=Decimal(10)),
            "fill",
            bar_duration=timedelta(minutes=minutes),
            spread_bps=Decimal(spread),
            latency_ms=1,
            volume_participation=Decimal("0.1"),
        )
    )
    assert isinstance(decision, FilledExecution)
    assert decision.fill.timestamp == (close - timedelta(minutes=minutes) if at_open else close)
    assert decision.triggered_at == (close - timedelta(minutes=minutes) if state == "gap" else None)
    assert (
        decision.fill.execution_price <= Decimal(limit)
        if buy
        else decision.fill.execution_price >= Decimal(limit)
    )


@pytest.mark.parametrize("minutes", [1, 5])
def test_range_fill_event_ledger_csv_holding_and_replay_share_close_time(
    minutes: int, tmp_path: Path
) -> None:
    class RoundTripStrategy:
        def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
            if len(context.history) == 1:
                return (
                    order(
                        order_type="stop_limit",
                        stop_price="110",
                        limit_price="115",
                        time_in_force="gtc",
                    ).intent,
                )
            if len(context.history) == 2:
                return (order(side="sell", submitted_at=context.current_bar.timestamp).intent,)
            return ()

    step = timedelta(minutes=minutes)
    bars = (
        event(timestamp=NOW),
        event(price="120", high="125", low="100", close="121", timestamp=NOW + step),
        event(price="122", timestamp=NOW + 2 * step),
    )
    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=Decimal(1000), bar_interval=f"{minutes}m")),
        RoundTripStrategy(),
    )
    assert result.orders[0].triggered_at == NOW
    assert result.fills[0].timestamp == NOW + step
    assert result.fills[1].timestamp == NOW + step
    assert [e.timestamp for e in result.events if e.kind == "fill"] == [NOW + step, NOW + step]
    ledger = next(e for e in result.events if e.kind == "ledger_update")
    assert ledger.timestamp == NOW + step
    assert ledger.cash == Decimal(770)
    assert ledger.equity == Decimal(1012)  # 770 cash + 2 shares marked at close=121
    assert round_trips(result.fills)[0].holding_seconds == 0
    # Replay uses exact timestamp equality against the close-labelled price bars.
    assert [b.timestamp for b in bars if b.timestamp == result.fills[0].timestamp] == [NOW + step]
    report = SimulationService(tmp_path, code_revision="test").run(request())
    report = report.model_copy(update={"result": result})
    assert str(NOW + step) in export_csv(report, "fills")
    assert str(NOW) in export_csv(report, "orders")
