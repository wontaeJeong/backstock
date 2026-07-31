from datetime import UTC, datetime
from decimal import Decimal
from typing import override

from packages.backtest.engine import BacktestEngine
from packages.backtest.events import EventKind
from packages.backtest.models import (
    BacktestConfig,
    BacktestInput,
    CostConfig,
    OrderIntent,
    OrderState,
    OrderType,
    Side,
    SnapshotReference,
)
from packages.backtest.ports import EvaluationContext, StrategyEvaluator
from packages.domain.market_data import AdjustmentMode, Bar


def _bar(
    instrument_id: str,
    day: int,
    *,
    open_: str,
    close: str,
    bounds: tuple[str, str] | None = None,
) -> Bar:
    parsed_open = Decimal(open_)
    parsed_close = Decimal(close)
    high, low = (
        bounds
        if bounds is not None
        else (
            str(max(parsed_open, parsed_close)),
            str(min(parsed_open, parsed_close)),
        )
    )
    return Bar(
        instrument_id=instrument_id,
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=parsed_open,
        high=Decimal(high),
        low=Decimal(low),
        close=parsed_close,
        volume=1000,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


def _input(bars: tuple[Bar, ...], config: BacktestConfig) -> BacktestInput:
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


class BuyThenHold(StrategyEvaluator):
    quantity: int
    order_type: OrderType
    limit_price: Decimal | None

    def __init__(
        self,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Decimal | None = None,
    ) -> None:
        self.quantity = quantity
        self.order_type = order_type
        self.limit_price = limit_price

    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
        instrument_history = tuple(
            bar for bar in context.history if bar.instrument_id == context.current_bar.instrument_id
        )
        if len(instrument_history) != 1:
            return ()
        return (
            OrderIntent(
                instrument_id=context.current_bar.instrument_id,
                submitted_at=context.current_bar.timestamp,
                side=Side.BUY,
                quantity=self.quantity,
                order_type=self.order_type,
                limit_price=self.limit_price,
                reason="first close entry",
            ),
        )


class BuyThenSell(StrategyEvaluator):
    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
        count = sum(
            bar.instrument_id == context.current_bar.instrument_id for bar in context.history
        )
        if count == 1:
            side = Side.BUY
        elif count == 2:
            side = Side.SELL
        else:
            return ()
        return (
            OrderIntent(
                instrument_id=context.current_bar.instrument_id,
                submitted_at=context.current_bar.timestamp,
                side=side,
                quantity=5,
                order_type=OrderType.MARKET,
                reason=f"{side.value} fixture",
            ),
        )


def test_buy_and_hold_golden_executes_at_next_open() -> None:
    bars = (
        _bar("AAA", 1, open_="100", close="100"),
        _bar("AAA", 2, open_="110", close="111"),
        _bar("AAA", 3, open_="120", close="120"),
    )

    result = BacktestEngine().run(
        _input(
            bars,
            BacktestConfig(initial_cash=Decimal(1000), benchmark_instrument_id="AAA"),
        ),
        BuyThenHold(5),
    )

    assert result.fills[0].timestamp == bars[1].timestamp
    assert result.fills[0].execution_price == Decimal(110)
    assert result.summary.final_equity == Decimal(1050)
    assert result.summary.total_return == Decimal("0.05")
    assert result.summary.unrealized_pnl == Decimal(50)
    assert result.benchmark[-1].value == Decimal(1200)
    kinds = [event.kind for event in result.events]
    assert kinds.index(EventKind.ORDER_INTENT) < kinds.index(EventKind.FILL)
    day_two_kinds = [event.kind for event in result.events if event.timestamp == bars[1].timestamp]
    assert day_two_kinds.index(EventKind.MARKET) < day_two_kinds.index(EventKind.FILL)


def test_round_trip_cost_golden_reports_net_realized_pnl() -> None:
    bars = (
        _bar("AAA", 1, open_="90", close="95"),
        _bar("AAA", 2, open_="100", close="105"),
        _bar("AAA", 3, open_="110", close="110"),
    )
    costs = CostConfig(commission_rate=Decimal("0.01"), sell_tax_rate=Decimal("0.005"))

    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=Decimal(1000), costs=costs)),
        BuyThenSell(),
    )

    assert result.summary.final_equity == Decimal("1036.750")
    assert result.summary.realized_pnl == Decimal("36.750")
    assert result.summary.commission == Decimal("10.500")
    assert result.summary.tax == Decimal("2.750")
    assert result.portfolio[-1].positions == ()


def test_unfilled_day_limit_expires_without_changing_ledger() -> None:
    bars = (
        _bar("AAA", 1, open_="100", close="100"),
        _bar("AAA", 2, open_="100", bounds=("105", "96"), close="102"),
    )

    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=Decimal(1000))),
        BuyThenHold(5, OrderType.LIMIT, Decimal(95)),
    )

    assert result.orders[0].state is OrderState.EXPIRED
    assert result.fills == ()
    assert result.summary.final_equity == Decimal(1000)


def test_multi_symbol_execution_is_canonical_and_isolated() -> None:
    bars = (
        _bar("BBB", 1, open_="50", close="50"),
        _bar("AAA", 1, open_="100", close="100"),
        _bar("BBB", 2, open_="50", close="50"),
        _bar("AAA", 2, open_="100", close="100"),
        _bar("AAA", 3, open_="110", close="110"),
        _bar("BBB", 3, open_="40", close="40"),
    )

    result = BacktestEngine().run(
        _input(bars, BacktestConfig(initial_cash=Decimal(500))),
        BuyThenHold(2),
    )

    assert [fill.instrument_id for fill in result.fills] == ["AAA", "BBB"]
    assert result.portfolio[-1].cash == Decimal(200)
    assert result.portfolio[-1].market_value == Decimal(300)
    assert result.portfolio[-1].equity == Decimal(500)
