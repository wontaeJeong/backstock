from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import override

import pytest

from packages.backtest.engine import BacktestEngine
from packages.backtest.events import EventKind
from packages.backtest.models import (
    BacktestConfig,
    BacktestInput,
    CancelIntent,
    CostConfig,
    EndPositionPolicy,
    OrderIntent,
    OrderState,
    OrderType,
    RunStatus,
    Side,
    SnapshotReference,
    TimeInForce,
)
from packages.backtest.ports import (
    CancellationProbe,
    EvaluationContext,
    StrategyEvaluationError,
    StrategyEvaluator,
)
from packages.domain.market_data import AdjustmentMode, Bar

STRATEGY_FAILURE = "fixture strategy failed"


def _bars() -> tuple[Bar, ...]:
    return tuple(
        Bar(
            instrument_id="AAA",
            timestamp=datetime(2024, 1, day, tzinfo=UTC),
            open=Decimal(price),
            high=Decimal(price),
            low=Decimal(price),
            close=Decimal(price),
            volume=1000,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        )
        for day, price in ((1, "100"), (2, "100"), (3, "110"))
    )


def _input(config: BacktestConfig) -> BacktestInput:
    return BacktestInput(
        snapshot=SnapshotReference(
            snapshot_id="a" * 64,
            normalized_checksum=f"sha256:{'b' * 64}",
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        bars=_bars(),
        config=config,
        strategy_version="strategy-v1",
        code_revision="test-revision",
    )


class BuyQuantity(StrategyEvaluator):
    quantity: int

    def __init__(self, quantity: int) -> None:
        self.quantity = quantity

    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
        if len(context.history) != 1:
            return ()
        return (
            OrderIntent(
                instrument_id="AAA",
                submitted_at=context.current_bar.timestamp,
                side=Side.BUY,
                quantity=self.quantity,
                order_type=OrderType.MARKET,
                reason="fixture buy",
            ),
        )


class FailingStrategy(StrategyEvaluator):
    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
        del context
        raise StrategyEvaluationError(STRATEGY_FAILURE)


class CancelAfterFirstBar(CancellationProbe):
    @override
    def should_cancel(self, processed_events: int) -> bool:
        return processed_events >= 4


class CancelPendingLimit(StrategyEvaluator):
    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent | CancelIntent, ...]:
        if len(context.history) == 1:
            return (
                OrderIntent(
                    instrument_id="AAA",
                    submitted_at=context.current_bar.timestamp,
                    side=Side.BUY,
                    quantity=1,
                    order_type=OrderType.LIMIT,
                    limit_price=Decimal(90),
                    time_in_force=TimeInForce.GTC,
                    reason="resting limit",
                ),
            )
        if len(context.history) == 2:
            return (
                CancelIntent(
                    order_id="order-000001",
                    submitted_at=context.current_bar.timestamp,
                    reason="strategy cancelled",
                ),
            )
        return ()


class CancelWithOffset(StrategyEvaluator):
    offset: timedelta

    def __init__(self, offset: timedelta) -> None:
        self.offset = offset

    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent | CancelIntent, ...]:
        if len(context.history) == 1:
            return (
                OrderIntent(
                    instrument_id="AAA",
                    submitted_at=context.current_bar.timestamp,
                    side=Side.BUY,
                    quantity=1,
                    order_type=OrderType.LIMIT,
                    limit_price=Decimal(90),
                    time_in_force=TimeInForce.GTC,
                    reason="resting limit",
                ),
            )
        if len(context.history) == 2:
            return (
                CancelIntent(
                    order_id="order-000001",
                    submitted_at=context.current_bar.timestamp + self.offset,
                    reason="invalid-time cancellation",
                ),
            )
        return ()


def test_engine_rejects_buy_when_fees_exceed_available_cash() -> None:
    result = BacktestEngine().run(
        _input(
            BacktestConfig(
                initial_cash=Decimal(1000),
                costs=CostConfig(commission_rate=Decimal("0.01")),
            )
        ),
        BuyQuantity(10),
    )

    assert result.orders[0].state is OrderState.REJECTED
    assert result.fills == ()
    assert result.summary.final_equity == Decimal(1000)
    assert EventKind.ORDER_REJECTED in {event.kind for event in result.events}


def test_engine_returns_auditable_cancelled_result() -> None:
    result = BacktestEngine().run(
        _input(BacktestConfig(initial_cash=Decimal(1000))),
        BuyQuantity(1),
        CancelAfterFirstBar(),
    )

    assert result.status is RunStatus.CANCELLED
    assert result.fills == ()
    assert result.events[-1].kind is EventKind.RUN_CANCELLED


def test_engine_returns_failed_result_for_typed_strategy_failure() -> None:
    result = BacktestEngine().run(
        _input(BacktestConfig(initial_cash=Decimal(1000))),
        FailingStrategy(),
    )

    assert result.status is RunStatus.FAILED
    assert result.failure_reason == STRATEGY_FAILURE
    assert result.events[-1].kind is EventKind.RUN_FAILED


def test_strategy_can_cancel_a_gtc_order_before_later_touch() -> None:
    result = BacktestEngine().run(
        _input(BacktestConfig(initial_cash=Decimal(1000))),
        CancelPendingLimit(),
    )

    assert result.orders[0].state is OrderState.CANCELLED
    assert result.fills == ()


@pytest.mark.parametrize("offset", [timedelta(days=-1), timedelta(days=1)])
def test_engine_rejects_cancel_intent_outside_current_bar(offset: timedelta) -> None:
    bars = _bars()

    result = BacktestEngine().run(
        _input(BacktestConfig(initial_cash=Decimal(1000))),
        CancelWithOffset(offset),
    )

    rejection = next(
        event for event in result.events if event.kind is EventKind.ORDER_CANCEL_REJECTED
    )
    assert rejection.timestamp == bars[1].timestamp
    assert result.orders[0].state is OrderState.EXPIRED


def test_end_policy_can_liquidate_open_positions_at_last_close() -> None:
    result = BacktestEngine().run(
        _input(
            BacktestConfig(
                initial_cash=Decimal(1000),
                end_position_policy=EndPositionPolicy.LIQUIDATE_AT_LAST_CLOSE,
            )
        ),
        BuyQuantity(5),
    )

    assert [fill.side for fill in result.fills] == [Side.BUY, Side.SELL]
    assert result.fills[-1].execution_price == Decimal(110)
    assert result.portfolio[-1].positions == ()
    assert result.summary.realized_pnl == Decimal(50)
