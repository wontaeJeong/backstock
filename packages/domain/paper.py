"""Pure, long-only manual/historical paper ledger. Never a live execution model."""

# Error literals are typed public codes, never interpolated request content.
# ruff: noqa: EM101

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field

Price = Annotated[Decimal, Field(gt=0, le=1_000_000, max_digits=13, decimal_places=6)]
Cash = Annotated[Decimal, Field(gt=0, le=1_000_000_000, max_digits=16, decimal_places=6)]
Quantity = Annotated[int, Field(strict=True, ge=1, le=1_000_000)]
Symbol = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9.:-]{0,31}$")]
Side = Literal["buy", "sell"]
OrderState = Literal["pending_approval", "filled", "rejected", "cancelled", "risk_rejected"]
PaperCode = Literal[
    "INSUFFICIENT_CASH",
    "INSUFFICIENT_POSITION",
    "NOTIONAL_LIMIT",
    "KILL_SWITCH",
    "INVALID_TRANSITION",
    "NOT_FOUND",
    "IDEMPOTENCY_CONFLICT",
    "CAPACITY_LIMIT",
    "PAPER_DISABLED",
    "PAPER_STORAGE_ERROR",
    "PAPER_INTEGRITY_ERROR",
]


class PaperRuleError(Exception):
    def __init__(self, code: PaperCode) -> None:
        """Expose only an allowlisted safety code."""
        self.code = code
        super().__init__(code)


class PaperModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


MAX_NOTIONAL = Decimal(1_000_000)


class Costs(PaperModel):
    commission_bps: Annotated[Decimal, Field(ge=0, le=100, max_digits=6, decimal_places=3)] = (
        Decimal(1)
    )
    sell_tax_bps: Annotated[Decimal, Field(ge=0, le=100, max_digits=6, decimal_places=3)] = Decimal(
        0
    )
    slippage_bps: Annotated[Decimal, Field(ge=0, le=100, max_digits=6, decimal_places=3)] = Decimal(
        5
    )


class Quote(PaperModel):
    symbol: Symbol
    price: Price
    quote_at: AwareDatetime
    source: Literal["manual_historical_paper"] = "manual_historical_paper"


class PaperOrder(PaperModel):
    order_id: str
    symbol: Symbol
    side: Side
    quantity: Quantity
    reference_price: Price
    quote_at: AwareDatetime
    created_at: AwareDatetime
    state: OrderState = "pending_approval"
    reason: PaperCode | None = None


class PaperFill(PaperModel):
    fill_id: str
    order_id: str
    symbol: Symbol
    side: Side
    quantity: Quantity
    reference_price: Decimal
    execution_price: Decimal
    commission: Decimal
    tax: Decimal
    slippage: Decimal
    quote_at: AwareDatetime
    approved_at: AwareDatetime
    source: Literal["manual_historical_paper"] = "manual_historical_paper"


class Position(PaperModel):
    symbol: Symbol
    quantity: int
    cost_basis: Decimal
    mark: Quote

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_cost(self) -> Decimal:
        return self.cost_basis / self.quantity

    @computed_field  # type: ignore[prop-decorator]
    @property
    def market_value(self) -> Decimal:
        return self.mark.price * self.quantity

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unrealized_pnl(self) -> Decimal:
        return self.market_value - self.cost_basis


class AuditEvent(PaperModel):
    sequence: int
    at: AwareDatetime
    kind: Literal[
        "account_created",
        "proposal_created",
        "approved_paper_fill",
        "rejected",
        "cancelled",
        "risk_rejected",
        "quote_marked",
        "kill_switch",
        "request_denied",
    ]
    order_id: str | None = None
    code: PaperCode | None = None


class PaperAccount(PaperModel):
    account_id: str
    name: str
    initial_cash: Decimal
    cash: Decimal
    costs: Costs = Costs()
    positions: tuple[Position, ...] = ()
    orders: tuple[PaperOrder, ...] = ()
    fills: tuple[PaperFill, ...] = ()
    quotes: tuple[Quote, ...] = ()
    audit: tuple[AuditEvent, ...] = ()
    kill_switch: bool = False
    realized_pnl: Decimal = Decimal(0)
    mode: Literal["paper"] = "paper"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def equity(self) -> Decimal:
        return self.cash + sum((p.market_value for p in self.positions), Decimal(0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def commission(self) -> Decimal:
        return sum((f.commission for f in self.fills), Decimal(0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tax(self) -> Decimal:
        return sum((f.tax for f in self.fills), Decimal(0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slippage(self) -> Decimal:
        return sum((f.slippage for f in self.fills), Decimal(0))


def audit(account: PaperAccount, event: AuditEvent) -> PaperAccount:
    return account.model_copy(update={"audit": (*account.audit, event)})


def propose(account: PaperAccount, order: PaperOrder) -> PaperAccount:
    if account.kill_switch:
        raise PaperRuleError("KILL_SWITCH")
    if order.quantity * order.reference_price > MAX_NOTIONAL:
        raise PaperRuleError("NOTIONAL_LIMIT")
    return account.model_copy(update={"orders": (*account.orders, order)})


def set_order(account: PaperAccount, order: PaperOrder) -> PaperAccount:
    return account.model_copy(
        update={
            "orders": tuple(order if o.order_id == order.order_id else o for o in account.orders)
        }
    )


def mark_quote(account: PaperAccount, quote: Quote) -> PaperAccount:
    return account.model_copy(
        update={
            "quotes": (*tuple(q for q in account.quotes if q.symbol != quote.symbol), quote),
            "positions": tuple(
                p.model_copy(update={"mark": quote}) if p.symbol == quote.symbol else p
                for p in account.positions
            ),
        }
    )


def apply_fill(account: PaperAccount, fill: PaperFill) -> PaperAccount:
    """Apply cash and cost basis once; caller owns transition/idempotency boundary."""
    position = next((p for p in account.positions if p.symbol == fill.symbol), None)
    quantity = position.quantity if position else 0
    basis = position.cost_basis if position else Decimal(0)
    notional = fill.execution_price * fill.quantity
    fees = fill.commission + fill.tax
    realized = account.realized_pnl
    if fill.side == "buy":
        cash = account.cash - notional - fees
        if cash < 0:
            raise PaperRuleError("INSUFFICIENT_CASH")
        quantity += fill.quantity
        basis += notional + fees
    else:
        if quantity < fill.quantity:
            raise PaperRuleError("INSUFFICIENT_POSITION")
        removed = basis if quantity == fill.quantity else basis * fill.quantity / quantity
        quantity -= fill.quantity
        basis -= removed
        cash = account.cash + notional - fees
        realized += notional - fees - removed
    quote = next((q for q in account.quotes if q.symbol == fill.symbol), None)
    quote = quote or Quote(symbol=fill.symbol, price=fill.reference_price, quote_at=fill.quote_at)
    positions = tuple(p for p in account.positions if p.symbol != fill.symbol)
    if quantity:
        positions = (
            *positions,
            Position(symbol=fill.symbol, quantity=quantity, cost_basis=basis, mark=quote),
        )
    return account.model_copy(
        update={
            "cash": cash,
            "positions": positions,
            "realized_pnl": realized,
            "fills": (*account.fills, fill),
        }
    )


def approve(account: PaperAccount, order: PaperOrder, at: datetime) -> PaperAccount:
    if account.kill_switch:
        raise PaperRuleError("KILL_SWITCH")
    current = next((o for o in account.orders if o.order_id == order.order_id), None)
    if current is None:
        raise PaperRuleError("NOT_FOUND")
    if current != order or current.state != "pending_approval":
        raise PaperRuleError("INVALID_TRANSITION")
    if order.quantity * order.reference_price > MAX_NOTIONAL:
        raise PaperRuleError("NOTIONAL_LIMIT")
    direction = Decimal(1) if order.side == "buy" else Decimal(-1)
    price = (
        order.reference_price * (1 + direction * account.costs.slippage_bps / 10000)
    ).normalize()
    notional = price * order.quantity
    if notional > MAX_NOTIONAL:
        raise PaperRuleError("NOTIONAL_LIMIT")
    fill = PaperFill(
        fill_id=f"paper_fill_{order.order_id.removeprefix('paper_order_')}",
        order_id=order.order_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        reference_price=order.reference_price,
        execution_price=price,
        commission=notional * account.costs.commission_bps / 10000,
        tax=notional * account.costs.sell_tax_bps / 10000 if order.side == "sell" else Decimal(0),
        slippage=abs(price - order.reference_price) * order.quantity,
        quote_at=order.quote_at,
        approved_at=at,
    )
    return set_order(apply_fill(account, fill), order.model_copy(update={"state": "filled"}))


class Reconciliation(PaperModel):
    account_id: str
    scope: Literal["internal_paper_ledger"] = "internal_paper_ledger"
    consistent: bool
    expected_cash: Decimal
    actual_cash: Decimal
    expected_positions: dict[str, int]
    actual_positions: dict[str, int]
    issues: tuple[str, ...]


def reconcile(account: PaperAccount) -> Reconciliation:
    ledger = PaperAccount(
        account_id=account.account_id,
        name=account.name,
        initial_cash=account.initial_cash,
        cash=account.initial_cash,
    )
    issues: list[str] = []
    for fill in account.fills:
        try:
            ledger = apply_fill(ledger, fill)
        except PaperRuleError:
            issues.append("invalid_fill_ledger")
            break
    expected = {p.symbol: p.quantity for p in ledger.positions}
    actual = {p.symbol: p.quantity for p in account.positions}
    if ledger.cash != account.cash:
        issues.append("cash_mismatch")
    if expected != actual:
        issues.append("position_mismatch")
    if {p.symbol: p.cost_basis for p in ledger.positions} != {
        p.symbol: p.cost_basis for p in account.positions
    } or ledger.realized_pnl != account.realized_pnl:
        issues.append("cost_basis_or_realized_mismatch")
    filled_orders = {o.order_id for o in account.orders if o.state == "filled"}
    fill_orders = [f.order_id for f in account.fills]
    if filled_orders != set(fill_orders) or len(fill_orders) != len(set(fill_orders)):
        issues.append("order_fill_mismatch")
    approval_orders = [a.order_id for a in account.audit if a.kind == "approved_paper_fill"]
    if set(approval_orders) != filled_orders or len(approval_orders) != len(fill_orders):
        issues.append("approval_audit_mismatch")
    return Reconciliation(
        account_id=account.account_id,
        consistent=not issues,
        expected_cash=ledger.cash,
        actual_cash=account.cash,
        expected_positions=expected,
        actual_positions=actual,
        issues=tuple(issues),
    )
