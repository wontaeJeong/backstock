from datetime import datetime
from decimal import Decimal

from packages.backtest.models import (
    Fill,
    PortfolioSnapshot,
    PortfolioState,
    Position,
    PriceMark,
    Side,
)


class InsufficientCashError(Exception):
    pass


class InsufficientPositionError(Exception):
    pass


class MissingPriceMarkError(Exception):
    instrument_id: str

    def __init__(self, instrument_id: str) -> None:
        """Preserve the missing instrument identifier for callers."""
        self.instrument_id = instrument_id
        super().__init__(f"missing price mark for {instrument_id}")


def apply_fill(state: PortfolioState, fill: Fill) -> PortfolioState:
    positions = {position.instrument_id: position for position in state.positions}
    current = positions.get(fill.instrument_id)
    notional = fill.execution_price * fill.quantity
    match fill.side:
        case Side.BUY:
            debit = notional + fill.commission + fill.tax
            if debit > state.cash:
                raise InsufficientCashError
            prior_quantity = 0 if current is None else current.quantity
            prior_cost = Decimal(0) if current is None else current.average_cost * prior_quantity
            quantity = prior_quantity + fill.quantity
            positions[fill.instrument_id] = Position(
                instrument_id=fill.instrument_id,
                quantity=quantity,
                average_cost=(prior_cost + debit) / quantity,
            )
            cash = state.cash - debit
            realized_pnl = state.realized_pnl
        case Side.SELL:
            if current is None or current.quantity < fill.quantity:
                raise InsufficientPositionError
            proceeds = notional - fill.commission - fill.tax
            cash = state.cash + proceeds
            realized_pnl = state.realized_pnl + proceeds - current.average_cost * fill.quantity
            remaining = current.quantity - fill.quantity
            if remaining == 0:
                del positions[fill.instrument_id]
            else:
                positions[fill.instrument_id] = current.model_copy(update={"quantity": remaining})
    return PortfolioState(
        cash=cash,
        positions=tuple(positions[key] for key in sorted(positions)),
        realized_pnl=realized_pnl,
        total_commission=state.total_commission + fill.commission,
        total_tax=state.total_tax + fill.tax,
        total_slippage=state.total_slippage + fill.slippage,
        total_spread=state.total_spread + fill.spread,
    )


def mark_portfolio(
    state: PortfolioState,
    *,
    timestamp: datetime,
    marks: tuple[PriceMark, ...],
) -> PortfolioSnapshot:
    prices = {mark.instrument_id: mark.price for mark in marks}
    market_value = Decimal(0)
    unrealized_pnl = Decimal(0)
    for position in state.positions:
        price = prices.get(position.instrument_id)
        if price is None:
            raise MissingPriceMarkError(position.instrument_id)
        market_value += price * position.quantity
        unrealized_pnl += (price - position.average_cost) * position.quantity
    return PortfolioSnapshot(
        timestamp=timestamp,
        cash=state.cash,
        market_value=market_value,
        equity=state.cash + market_value,
        realized_pnl=state.realized_pnl,
        unrealized_pnl=unrealized_pnl,
        positions=state.positions,
    )
