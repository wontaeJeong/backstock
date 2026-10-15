from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.application.simulation_history import HistoryEvaluator
from packages.backtest.engine import BacktestEngine
from packages.backtest.models import BacktestConfig
from packages.strategy.evaluator import DslStrategyEvaluator
from packages.strategy.schema import StrategyDefinition
from tests.application.test_simulations import definition
from tests.backtest.test_engine_golden import _input
from tests.research.test_execution_features import event

D = Decimal
START = datetime(2024, 1, 2, 20, 52, tzinfo=UTC)


def strategy(kind: str) -> StrategyDefinition:
    payload = definition("tick").model_dump(mode="json")
    payload["exit"] = payload["entry"]
    payload["session"] = {"entry_start": "15:52", "entry_end": "15:53", "flatten_at": "15:55"}
    payload["order"] = {"order_type": kind, "time_in_force": "gtc"}
    if kind in {"limit", "stop_limit"}:
        payload["order"]["limit_offset_bps"] = 0
    if kind in {"stop", "stop_limit"}:
        payload["order"]["stop_offset_bps"] = 0
    return StrategyDefinition.model_validate(payload)


@pytest.mark.parametrize("kind", ["limit", "stop", "stop_limit"])
@pytest.mark.parametrize("latency_ms", [0, 60_000])
@pytest.mark.parametrize("cap", [False, True])
def test_flatten_cancels_pending_exit_once_and_keeps_delayed_market_order(
    kind: str, latency_ms: int, *, cap: bool
) -> None:
    bars = tuple(
        event(
            price="100" if index < 2 else "90" if kind == "limit" else "110",
            volume=0 if cap and index in {4, 5} else 100,
            timestamp=START + timedelta(minutes=index),
        )
        for index in range(7)
    )
    result = BacktestEngine().run(
        _input(
            bars,
            BacktestConfig(
                initial_cash=D(1000),
                bar_interval="tick",
                latency_ms=latency_ms,
                volume_participation=D("0.1") if cap else None,
            ),
        ),
        HistoryEvaluator(DslStrategyEvaluator(strategy(kind)), ()),
    )
    assert [fill.side for fill in result.fills] == ["buy", "sell"]
    exits = [o for o in result.orders if o.intent.rule_path == "session/flatten"]
    assert len(exits) == 1
    assert exits[0].state == "filled"
    assert exits[0].intent.submitted_at == START + timedelta(minutes=3)
    assert result.fills[-1].timestamp == START + timedelta(minutes=6 if cap else 4)
    replaced = [o for o in result.orders if o.state == "cancelled"]
    assert len(replaced) == 1
    assert replaced[0].intent.order_type == kind
    cancel_events = [e for e in result.events if e.kind == "order_cancelled"]
    assert len(cancel_events) == 1
    assert cancel_events[0].order_id == replaced[0].order_id
    assert cancel_events[0].sequence < next(
        e.sequence
        for e in result.events
        if e.kind == "order_accepted" and e.order_id == exits[0].order_id
    )
    assert result.portfolio[-1].positions == ()
    assert all(position.quantity >= 0 for point in result.portfolio for position in point.positions)


@pytest.mark.parametrize("kind", ["limit", "stop", "stop_limit"])
def test_flatten_replacement_without_next_event_expires_not_same_close_fill(kind: str) -> None:
    bars = tuple(
        event(
            price="100" if index < 2 else "90" if kind == "limit" else "110",
            timestamp=START + timedelta(minutes=index),
        )
        for index in range(4)
    )
    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=D(1000), bar_interval="tick")),
        DslStrategyEvaluator(strategy(kind)),
    )
    assert len(result.fills) == 1
    assert result.orders[-1].intent.rule_path == "session/flatten"
    assert result.orders[-1].state == "expired"
    assert any(o.state == "cancelled" for o in result.orders)
    assert result.portfolio[-1].positions[0].quantity == 2


def test_flatten_boundary_cancels_still_pending_entry_before_later_touch() -> None:
    payload = strategy("stop").model_dump(mode="json")
    payload["order"]["stop_offset_bps"] = 500
    bars = tuple(
        event(price="100" if index < 4 else "110", timestamp=START + timedelta(minutes=index))
        for index in range(6)
    )
    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=D(1000), bar_interval="tick")),
        DslStrategyEvaluator(StrategyDefinition.model_validate(payload)),
    )
    assert result.fills == ()
    assert result.orders[0].state == "cancelled"
    assert [e.timestamp for e in result.events if e.kind == "order_cancelled"] == [
        START + timedelta(minutes=3)
    ]
