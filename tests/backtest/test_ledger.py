from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.backtest.ledger import InsufficientCashError, apply_fill, mark_portfolio
from packages.backtest.models import Fill, PortfolioState, PriceMark, Side


def _fill(
    side: Side,
    price: str,
    *,
    quantity: int = 5,
    commission: str = "0",
    tax: str = "0",
) -> Fill:
    parsed_price = Decimal(price)
    return Fill(
        fill_id=f"fill-{side.value}",
        order_id=f"order-{side.value}",
        instrument_id="AAA",
        timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        side=side,
        quantity=quantity,
        reference_price=parsed_price,
        execution_price=parsed_price,
        commission=Decimal(commission),
        tax=Decimal(tax),
        slippage=Decimal(0),
    )


def test_ledger_tracks_cash_cost_basis_and_realized_profit() -> None:
    initial = PortfolioState(cash=Decimal(1000))
    bought = apply_fill(initial, _fill(Side.BUY, "100", commission="5"))

    sold = apply_fill(bought, _fill(Side.SELL, "110", commission="5.50", tax="2.75"))

    assert bought.cash == Decimal(495)
    assert bought.positions[0].average_cost == Decimal(101)
    assert sold.cash == Decimal("1036.75")
    assert sold.realized_pnl == Decimal("36.75")
    assert sold.positions == ()


def test_ledger_rejects_buy_when_costs_exceed_cash() -> None:
    initial = PortfolioState(cash=Decimal(1000))

    with pytest.raises(InsufficientCashError):
        _ = apply_fill(
            initial,
            _fill(Side.BUY, "100", quantity=10, commission="10"),
        )


def test_portfolio_mark_preserves_equity_identity() -> None:
    state = apply_fill(PortfolioState(cash=Decimal(1000)), _fill(Side.BUY, "100"))

    snapshot = mark_portfolio(
        state,
        timestamp=datetime(2024, 1, 3, tzinfo=UTC),
        marks=(PriceMark(instrument_id="AAA", price=Decimal(110)),),
    )

    assert snapshot.cash == Decimal(500)
    assert snapshot.market_value == Decimal(550)
    assert snapshot.equity == Decimal(1050)
    assert snapshot.unrealized_pnl == Decimal(50)
