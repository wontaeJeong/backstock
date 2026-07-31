from datetime import UTC, datetime
from decimal import Decimal
from typing import override

from hypothesis import given, settings
from hypothesis import strategies as st

from packages.backtest.engine import BacktestEngine
from packages.backtest.ledger import apply_fill, mark_portfolio
from packages.backtest.models import (
    BacktestConfig,
    BacktestInput,
    Fill,
    OrderIntent,
    OrderType,
    PortfolioState,
    PriceMark,
    Side,
    SnapshotReference,
)
from packages.backtest.ports import EvaluationContext, StrategyEvaluator
from packages.domain.market_data import AdjustmentMode, Bar


def _bar(day: int, price: int) -> Bar:
    parsed = Decimal(price)
    return Bar(
        instrument_id="AAA",
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=parsed,
        high=parsed,
        low=parsed,
        close=parsed,
        volume=1000,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


def _input(prices: list[int], *, seed: int = 0) -> BacktestInput:
    return BacktestInput(
        snapshot=SnapshotReference(
            snapshot_id="a" * 64,
            normalized_checksum=f"sha256:{'b' * 64}",
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        bars=tuple(_bar(day, price) for day, price in enumerate(prices, start=1)),
        config=BacktestConfig(initial_cash=Decimal(1_000_000), seed=seed),
        strategy_version="property-strategy",
        code_revision="property-revision",
    )


class FirstBarBuyer(StrategyEvaluator):
    histories: list[tuple[Bar, ...]]

    def __init__(self) -> None:
        self.histories = []

    @override
    def evaluate(self, context: EvaluationContext) -> tuple[OrderIntent, ...]:
        self.histories.append(context.history)
        if len(context.history) != 1:
            return ()
        return (
            OrderIntent(
                instrument_id="AAA",
                submitted_at=context.current_bar.timestamp,
                side=Side.BUY,
                quantity=1,
                order_type=OrderType.MARKET,
                reason="property entry",
            ),
        )


@settings(max_examples=50, deadline=None)
@given(
    quantity=st.integers(min_value=1, max_value=100),
    buy_price=st.integers(min_value=1, max_value=10_000),
    sell_price=st.integers(min_value=1, max_value=10_000),
    commission_bps=st.integers(min_value=0, max_value=100),
)
def test_ledger_generated_round_trip_preserves_money_invariants(
    quantity: int, buy_price: int, sell_price: int, commission_bps: int
) -> None:
    rate = Decimal(commission_bps) / Decimal(10_000)
    buy_notional = Decimal(buy_price) * quantity
    initial_cash = buy_notional * (Decimal(1) + rate) + Decimal(1000)
    buy = Fill(
        fill_id="buy",
        order_id="buy-order",
        instrument_id="AAA",
        timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        side=Side.BUY,
        quantity=quantity,
        reference_price=Decimal(buy_price),
        execution_price=Decimal(buy_price),
        commission=buy_notional * rate,
        tax=Decimal(0),
        slippage=Decimal(0),
    )
    sell_notional = Decimal(sell_price) * quantity
    sell = Fill(
        fill_id="sell",
        order_id="sell-order",
        instrument_id="AAA",
        timestamp=datetime(2024, 1, 3, tzinfo=UTC),
        side=Side.SELL,
        quantity=quantity,
        reference_price=Decimal(sell_price),
        execution_price=Decimal(sell_price),
        commission=sell_notional * rate,
        tax=Decimal(0),
        slippage=Decimal(0),
    )

    bought = apply_fill(PortfolioState(cash=initial_cash), buy)
    marked = mark_portfolio(
        bought,
        timestamp=buy.timestamp,
        marks=(PriceMark(instrument_id="AAA", price=Decimal(sell_price)),),
    )
    sold = apply_fill(bought, sell)

    assert bought.cash >= 0
    assert bought.positions[0].quantity >= 0
    assert marked.equity == marked.cash + marked.market_value
    assert sold.cash - initial_cash == sold.realized_pnl
    assert sold.positions == ()
    assert isinstance(sold.cash, Decimal)


@settings(max_examples=30, deadline=None)
@given(prices=st.lists(st.integers(min_value=1, max_value=10_000), min_size=3, max_size=6))
def test_generated_runs_are_repeatable_and_never_expose_future_bars(prices: list[int]) -> None:
    first_strategy = FirstBarBuyer()
    second_strategy = FirstBarBuyer()
    backtest_input = _input(prices, seed=42)

    first = BacktestEngine().run(backtest_input, first_strategy)
    second = BacktestEngine().run(backtest_input, second_strategy)

    assert first == second
    assert first.fills[0].timestamp == backtest_input.bars[1].timestamp
    assert first.fills[0].execution_price == backtest_input.bars[1].open
    assert all(
        all(bar.timestamp <= history[-1].timestamp for bar in history)
        for history in first_strategy.histories
    )


@settings(max_examples=30, deadline=None)
@given(
    prefix=st.lists(st.integers(min_value=1, max_value=10_000), min_size=3, max_size=5),
    future_price=st.integers(min_value=1, max_value=10_000),
)
def test_appending_future_data_cannot_change_prior_events(
    prefix: list[int], future_price: int
) -> None:
    base = BacktestEngine().run(_input(prefix), FirstBarBuyer())
    extended = BacktestEngine().run(_input([*prefix, future_price]), FirstBarBuyer())
    boundary = datetime(2024, 1, len(prefix), tzinfo=UTC)

    base_events = tuple(event for event in base.events if event.timestamp <= boundary)
    extended_events = tuple(event for event in extended.events if event.timestamp <= boundary)
    base_fills = tuple(fill for fill in base.fills if fill.timestamp <= boundary)
    extended_fills = tuple(fill for fill in extended.fills if fill.timestamp <= boundary)

    assert extended_events == base_events
    assert extended_fills == base_fills
