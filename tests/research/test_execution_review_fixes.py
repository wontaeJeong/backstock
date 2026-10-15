from datetime import timedelta
from decimal import Decimal

import pytest

from packages.backtest.engine import BacktestEngine
from packages.backtest.execution import (
    ExecutionRequest,
    FilledExecution,
    PendingExecution,
    execute_order,
)
from packages.backtest.models import BacktestConfig, CostConfig, OrderIntent
from packages.backtest.ports import EvaluationContext
from tests.backtest.test_engine_golden import _input
from tests.research.test_execution_features import NOW, event, order

D = Decimal


@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("activated", [False, True])
def test_spread_adjusted_intrabar_limit_deep_cross_fills(side: str, *, activated: bool) -> None:
    pending = order(
        side=side,
        order_type="stop_limit" if activated else "limit",
        limit_price="100",
        **({"stop_price": "100"} if activated else {}),
    )
    if activated:
        pending = pending.model_copy(update={"triggered_at": NOW})
    bar = (
        event(price="105", low="90", high="110")
        if side == "buy"
        else event(price="95", low="90", high="110")
    )
    result = execute_order(
        ExecutionRequest(pending, bar, CostConfig(slippage_bps=D(10)), "f", spread_bps=D(10))
    )
    assert isinstance(result, FilledExecution)
    fill = result.fill
    assert fill.execution_price == 100
    assert fill.reference_price < 100 if side == "buy" else fill.reference_price > 100
    assert fill.spread > 0
    assert (
        abs(fill.execution_price - fill.reference_price) * fill.quantity
        == fill.spread + fill.slippage
    )


@pytest.mark.parametrize(
    ("side", "price", "low", "high"),
    [("buy", "105", "99.99", "110"), ("sell", "95", "90", "100.01")],
)
@pytest.mark.parametrize("activated", [False, True])
def test_raw_limit_touch_without_spread_penetration_remains_pending(
    side: str, price: str, low: str, high: str, *, activated: bool
) -> None:
    pending = order(
        side=side,
        order_type="stop_limit" if activated else "limit",
        limit_price="100",
        **({"stop_price": "100"} if activated else {}),
    )
    if activated:
        pending = pending.model_copy(update={"triggered_at": NOW})
    result = execute_order(
        ExecutionRequest(
            pending,
            event(price=price, low=low, high=high),
            CostConfig(),
            "f",
            spread_bps=D(10),
        )
    )
    assert isinstance(result, PendingExecution)


@pytest.mark.parametrize(("side", "price"), [("buy", "99"), ("sell", "101")])
def test_ohlc_open_improvement_spread_and_limit_clamped_slippage_reconcile(
    side: str, price: str
) -> None:
    result = execute_order(
        ExecutionRequest(
            order(side=side, order_type="limit", limit_price="100"),
            event(price=price),
            CostConfig(slippage_bps=D(200)),
            "f",
            spread_bps=D(10),
        )
    )
    assert isinstance(result, FilledExecution)
    fill = result.fill
    assert fill.execution_price == 100
    assert fill.reference_price == D(price)
    assert fill.spread == D(price) * D("0.0005") * fill.quantity
    assert fill.slippage > 0
    assert (
        abs(fill.execution_price - fill.reference_price) * fill.quantity
        == fill.spread + fill.slippage
    )


@pytest.mark.parametrize(
    ("side", "bid", "ask", "fills"),
    [
        ("buy", "99.9", "100.01", False),
        ("buy", "99.8", "99.9", True),
        ("sell", "99.99", "100.1", False),
        ("sell", "100.1", "100.2", True),
    ],
)
def test_real_quote_side_limit_is_not_clipped_to_fabricate_a_fill(
    side: str, bid: str, ask: str, *, fills: bool
) -> None:
    result = execute_order(
        ExecutionRequest(
            order(side=side, order_type="limit", limit_price="100"),
            event(bid=bid, ask=ask),
            CostConfig(slippage_bps=D(100)),
            "f",
            spread_bps=D(100),
        )
    )
    assert isinstance(result, FilledExecution) == fills
    if isinstance(result, FilledExecution):
        fill = result.fill
        assert fill.execution_price <= 100 if side == "buy" else fill.execution_price >= 100
        assert (
            abs(fill.execution_price - fill.reference_price) * fill.quantity
            == fill.spread + fill.slippage
        )


@pytest.mark.parametrize(
    ("side", "open_price", "expected"), [("buy", "99", "99"), ("sell", "101", "101")]
)
def test_zero_spread_limit_open_improvement_parity(
    side: str, open_price: str, expected: str
) -> None:
    result = execute_order(
        ExecutionRequest(
            order(side=side, order_type="limit", limit_price="100"),
            event(price=open_price),
            CostConfig(),
            "f",
        )
    )
    assert isinstance(result, FilledExecution)
    assert result.fill.execution_price == D(expected)
    assert result.fill.spread == result.fill.slippage == 0


@pytest.mark.parametrize("minutes", [1, 5])
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("kind", ["stop", "stop_limit"])
@pytest.mark.parametrize("gap", [True, False])
def test_pending_stop_decision_carries_known_open_or_conservative_close(
    minutes: int, side: str, kind: str, *, gap: bool
) -> None:
    stop = "105" if side == "buy" else "95"
    pending = order(
        side=side,
        order_type=kind,
        stop_price=stop,
        time_in_force="gtc",
        **({"limit_price": "100"} if kind == "stop_limit" else {}),
    )
    price = ("110" if side == "buy" else "90") if gap else "100"
    close_at = NOW + timedelta(minutes=minutes * 2)
    bar = event(price=price, high="110", low="90", volume=0, timestamp=close_at)
    decision = execute_order(
        ExecutionRequest(
            pending,
            bar,
            CostConfig(),
            "f",
            bar_duration=timedelta(minutes=minutes),
            volume_participation=D("0.1"),
        )
    )
    assert isinstance(decision, PendingExecution)
    assert decision.triggered
    assert decision.triggered_at == (close_at - timedelta(minutes=minutes) if gap else close_at)


@pytest.mark.parametrize("minutes", [1, 5])
@pytest.mark.parametrize("side", ["buy", "sell"])
def test_gap_limit_bound_wait_has_open_trigger_timestamp(minutes: int, side: str) -> None:
    price = "110" if side == "buy" else "90"
    close_at = NOW + timedelta(minutes=minutes * 2)
    pending = order(
        side=side,
        order_type="stop_limit",
        stop_price="105" if side == "buy" else "95",
        limit_price="100",
        time_in_force="gtc",
    )
    decision = execute_order(
        ExecutionRequest(
            pending,
            event(price=price, timestamp=close_at),
            CostConfig(),
            "f",
            bar_duration=timedelta(minutes=minutes),
        )
    )
    assert isinstance(decision, PendingExecution)
    assert decision.reason == "limit_not_touched"
    assert decision.triggered_at == close_at - timedelta(minutes=minutes)


def test_engine_keeps_gap_trigger_open_when_cap_defers_fill() -> None:
    class StopEntry:
        def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
            return (
                (order(order_type="stop", stop_price="105", time_in_force="gtc").intent,)
                if len(context.history) == 1
                else ()
            )

    bars = (
        event(timestamp=NOW),
        event(price="110", volume=0, timestamp=NOW + timedelta(minutes=2)),
        event(price="111", timestamp=NOW + timedelta(minutes=3)),
    )
    result = BacktestEngine().run(
        _input(
            bars,
            BacktestConfig(initial_cash=D(1000), bar_interval="1m", volume_participation=D("0.1")),
        ),
        StopEntry(),
    )
    assert result.orders[0].triggered_at == NOW + timedelta(minutes=1)
    assert [e.timestamp for e in result.events if e.kind == "order_triggered"] == [
        NOW + timedelta(minutes=1)
    ]
    assert result.fills[0].timestamp == NOW + timedelta(minutes=2)
