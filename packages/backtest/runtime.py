from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from packages.backtest.events import BacktestEvent, EventKind
from packages.backtest.ledger import mark_portfolio
from packages.backtest.models import (
    Fill,
    Order,
    PortfolioSnapshot,
    PortfolioState,
    PriceMark,
    RunStatus,
)
from packages.domain.market_data import Bar


@dataclass(frozen=True, slots=True)
class EventDetails:
    instrument_id: str | None = None
    order_id: str | None = None
    quantity: int | None = None
    reference_price: Decimal | None = None
    execution_price: Decimal | None = None
    commission: Decimal | None = None
    tax: Decimal | None = None
    slippage: Decimal | None = None
    spread: Decimal | None = None
    cash: Decimal | None = None
    equity: Decimal | None = None


@dataclass(slots=True)
class EngineState:
    """Mutable run accumulator isolated from reusable engine inputs and outputs."""

    portfolio: PortfolioState
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    events: list[BacktestEvent] = field(default_factory=list)
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    history: list[Bar] = field(default_factory=list)
    marks: dict[str, Decimal] = field(default_factory=dict)
    status: RunStatus = RunStatus.SUCCEEDED
    failure_reason: str | None = None

    def record(
        self,
        timestamp: datetime,
        kind: EventKind,
        reason: str,
        details: EventDetails | None = None,
    ) -> None:
        resolved = EventDetails() if details is None else details
        self.events.append(
            BacktestEvent(
                sequence=len(self.events) + 1,
                timestamp=timestamp,
                kind=kind,
                reason=reason,
                instrument_id=resolved.instrument_id,
                order_id=resolved.order_id,
                quantity=resolved.quantity,
                reference_price=resolved.reference_price,
                execution_price=resolved.execution_price,
                commission=resolved.commission,
                tax=resolved.tax,
                slippage=resolved.slippage,
                spread=resolved.spread,
                cash=resolved.cash,
                equity=resolved.equity,
            )
        )

    def mark(self, timestamp: datetime) -> PortfolioSnapshot:
        marks = tuple(
            PriceMark(instrument_id=instrument_id, price=self.marks[instrument_id])
            for instrument_id in sorted(self.marks)
        )
        return mark_portfolio(self.portfolio, timestamp=timestamp, marks=marks)

    def held_quantity(self, instrument_id: str) -> int:
        position = next(
            (item for item in self.portfolio.positions if item.instrument_id == instrument_id),
            None,
        )
        return 0 if position is None else position.quantity
