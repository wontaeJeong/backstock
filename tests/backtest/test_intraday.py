from datetime import UTC, datetime
from decimal import Decimal

from packages.backtest.engine import BacktestEngine
from packages.backtest.models import BacktestConfig, OrderIntent, OrderType, Side, TimeInForce
from packages.backtest.ports import EvaluationContext
from tests.backtest.test_engine_golden import BuyThenHold, _bar, _input


def test_intraday_day_limit_remains_pending_until_session_end() -> None:
    base = _bar("AAA", 1, open_="100", close="100")
    times = (
        datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 32, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 33, tzinfo=UTC),
    )
    bars = tuple(
        base.model_copy(update={"timestamp": time, "low": Decimal(low)})
        for time, low in zip(times, ("100", "100", "90"), strict=True)
    )
    config = BacktestConfig(initial_cash=Decimal(1000), bar_interval="1m")
    result = BacktestEngine().run(
        _input(bars, config), BuyThenHold(1, OrderType.LIMIT, Decimal(95))
    )
    assert len(result.fills) == 1
    # Open=100 is outside limit=95; only the later range establishes a touch.
    assert result.fills[0].timestamp == times[2]
    assert result.orders[0].state == "filled"


def test_intraday_day_limit_cannot_fill_in_later_session() -> None:
    base = _bar("AAA", 1, open_="100", close="100")
    bars = tuple(
        base.model_copy(
            update={
                "timestamp": datetime(2024, 1, day, 14, minute, tzinfo=UTC),
                "low": Decimal(low),
            }
        )
        for day, minute, low in ((2, 31, "100"), (2, 32, "100"), (3, 31, "90"))
    )
    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=Decimal(1000), bar_interval="1m")),
        BuyThenHold(1, OrderType.LIMIT, Decimal(95)),
    )
    assert result.fills == ()
    assert result.orders[0].state == "expired"


def test_repeated_entry_does_not_stack_pending_orders() -> None:
    class RepeatedEntry:
        def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
            return (
                OrderIntent(
                    instrument_id="AAA",
                    submitted_at=context.current_bar.timestamp,
                    side=Side.BUY,
                    quantity=1,
                    order_type=OrderType.LIMIT,
                    limit_price=Decimal(90),
                    time_in_force=TimeInForce.GTC,
                    reason="entry",
                ),
            )

    bars = tuple(_bar("AAA", day, open_="100", close="100") for day in range(1, 4))
    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=Decimal(1000))), RepeatedEntry()
    )
    assert result.orders[1].state == "rejected"
    assert result.orders[1].state_reason == "pending order already exists"
