from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from packages.backtest.engine import BacktestEngine
from packages.backtest.execution import (
    ExecutionRequest,
    FilledExecution,
    PendingExecution,
    execute_order,
)
from packages.backtest.models import BacktestConfig, CostConfig, Order, OrderIntent, Side
from packages.domain.market_data import AdjustmentMode, Bar
from packages.strategy.evaluator import DslStrategyEvaluator
from packages.strategy.schema import StrategyDefinition
from tests.application.test_simulations import definition
from tests.backtest.test_engine_golden import _input

D = Decimal
NOW = datetime(2024, 1, 2, 15, tzinfo=UTC)


def event(*, price: str = "100", volume: int = 100, **changes: object) -> Bar:
    return Bar.model_validate(
        {
            "instrument_id": "NASDAQ:AAPL",
            "timestamp": NOW + timedelta(seconds=1),
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
            "price_adjustment": AdjustmentMode.RAW,
            "volume_adjustment": AdjustmentMode.RAW,
            **changes,
        }
    )


def order(**changes: object) -> Order:
    return Order(
        order_id="order",
        intent=OrderIntent.model_validate(
            {
                "instrument_id": "NASDAQ:AAPL",
                "submitted_at": NOW,
                "side": "buy",
                "quantity": 2,
                "order_type": "market",
                "reason": "test",
                **changes,
            }
        ),
    )


def test_quote_midpoint_spread_and_slippage_are_disjoint_golden() -> None:
    decision = execute_order(
        ExecutionRequest(
            order(),
            event(bid="99", ask="101"),
            CostConfig(slippage_bps=D(10)),
            "fill",
            spread_bps=D(100),
        )
    )
    assert isinstance(decision, FilledExecution)
    assert decision.fill.reference_price == D(100)
    assert decision.fill.execution_price == D("101.101")
    assert decision.fill.spread == D(2)
    assert decision.fill.slippage == D("0.202")


def test_latency_uses_next_eligible_event_and_no_same_event() -> None:
    pending = execute_order(
        ExecutionRequest(order(), event(), CostConfig(), "fill", latency_ms=1001)
    )
    assert isinstance(pending, PendingExecution)
    ready = execute_order(
        ExecutionRequest(
            order(),
            event(timestamp=NOW + timedelta(seconds=2)),
            CostConfig(),
            "fill",
            latency_ms=1001,
        )
    )
    assert isinstance(ready, FilledExecution)
    same = execute_order(ExecutionRequest(order(), event(timestamp=NOW), CostConfig(), "fill"))
    assert isinstance(same, PendingExecution)


@given(st.integers(min_value=0, max_value=100))
def test_volume_cap_is_all_or_none(volume: int) -> None:
    decision = execute_order(
        ExecutionRequest(
            order(), event(volume=volume), CostConfig(), "fill", volume_participation=D("0.1")
        )
    )
    assert isinstance(decision, FilledExecution) == (volume >= 20)
    if isinstance(decision, FilledExecution):
        assert decision.fill.quantity == 2


def test_unlimited_default_still_fills_zero_volume() -> None:
    assert isinstance(
        execute_order(ExecutionRequest(order(), event(volume=0), CostConfig(), "f")),
        FilledExecution,
    )


def test_stop_gap_uses_adverse_open() -> None:
    intent = order(order_type="stop", stop_price="105")
    decision = execute_order(ExecutionRequest(intent, event(price="110"), CostConfig(), "f"))
    assert isinstance(decision, FilledExecution)
    assert decision.fill.execution_price == D(110)


def test_stop_limit_intrabar_trigger_defers_unknown_path() -> None:
    intent = order(order_type="stop_limit", stop_price="105", limit_price="103")
    decision = execute_order(
        ExecutionRequest(intent, event(high="110", low="99"), CostConfig(), "f")
    )
    assert isinstance(decision, PendingExecution)
    assert decision.triggered
    assert decision.reason == "stop_limit_intrabar_ambiguous"
    triggered = intent.model_copy(update={"triggered_at": NOW + timedelta(seconds=1)})
    next_fill = execute_order(
        ExecutionRequest(
            triggered, event(timestamp=NOW + timedelta(seconds=2), price="102"), CostConfig(), "f"
        )
    )
    assert isinstance(next_fill, FilledExecution)
    assert next_fill.fill.execution_price == D(102)


@pytest.mark.parametrize(
    "fields",
    [
        {"bid": "99"},
        {"bid": "102", "ask": "101"},
        {"bid": "0", "ask": "101"},
        {"bid": "99", "ask": "101", "price_adjustment": "split_adjusted"},
    ],
)
def test_invalid_quotes_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Bar.model_validate({**event().model_dump(), **fields})


def test_sell_spread_is_adverse() -> None:
    decision = execute_order(
        ExecutionRequest(order(side=Side.SELL), event(), CostConfig(), "f", spread_bps=D(100))
    )
    assert isinstance(decision, FilledExecution)
    assert decision.fill.execution_price == D("99.5")
    assert decision.fill.spread == D(1)


def test_order_contract_requires_explicit_trigger_and_limit() -> None:
    with pytest.raises(ValidationError):
        order(order_type="stop")
    with pytest.raises(ValidationError):
        order(stop_price="100")


def test_intrabar_stop_does_not_claim_trigger_at_bar_open() -> None:
    decision = execute_order(
        ExecutionRequest(
            order(order_type="stop", stop_price="105"),
            event(high="110", timestamp=NOW + timedelta(minutes=2)),
            CostConfig(),
            "f",
            bar_duration=timedelta(minutes=1),
        )
    )
    assert isinstance(decision, FilledExecution)
    assert decision.fill.timestamp == NOW + timedelta(minutes=2)


@given(st.integers(min_value=1, max_value=100), st.sampled_from(["buy", "sell"]))
def test_price_cost_components_reconcile_without_overlap(spread: int, side: str) -> None:
    decision = execute_order(
        ExecutionRequest(
            order(side=side), event(), CostConfig(slippage_bps=D(5)), "f", spread_bps=D(spread)
        )
    )
    assert isinstance(decision, FilledExecution)
    fill = decision.fill
    assert (
        abs(fill.execution_price - fill.reference_price) * fill.quantity
        == fill.spread + fill.slippage
    )


@pytest.mark.parametrize("kind", ["stop", "stop_limit"])
def test_engine_stop_trigger_trace_and_pending_dedupe(kind: str) -> None:
    payload = definition("1m").model_dump(mode="json")
    payload["order"] = {"order_type": kind, "stop_offset_bps": 500, "time_in_force": "gtc"}
    if kind == "stop_limit":
        payload["order"]["limit_offset_bps"] = 300
    strategy = StrategyDefinition.model_validate(payload)
    bars = (
        event(timestamp=NOW),
        event(high="110", low="99", timestamp=NOW + timedelta(minutes=1)),
        event(price="102", timestamp=NOW + timedelta(minutes=2)),
    )
    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=D(1000), bar_interval="1m")),
        DslStrategyEvaluator(strategy),
    )
    assert len(result.fills) == 1
    assert result.orders[0].triggered_at is not None
    assert len([e for e in result.events if e.kind == "order_triggered"]) == 1
    if kind == "stop_limit":
        assert result.fills[0].execution_price == 102
        assert result.orders[1].state == "rejected"
        assert "pending" in result.orders[1].state_reason
