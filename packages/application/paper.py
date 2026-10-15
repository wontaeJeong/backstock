"""Paper use cases and transactional persistence port; no concrete adapter dependency."""

# Error literals are allowlisted codes, not free-form exception messages.
# ruff: noqa: EM101

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol
from uuid import uuid4

from pydantic import AwareDatetime, Field, field_validator

from packages.domain.paper import (
    AuditEvent,
    Cash,
    Costs,
    PaperAccount,
    PaperCode,
    PaperModel,
    PaperOrder,
    PaperRuleError,
    Price,
    Quantity,
    Quote,
    Reconciliation,
    Side,
    Symbol,
    approve,
    audit,
    mark_quote,
    propose,
    reconcile,
    set_order,
)

Key = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
Operation = Literal["proposal", "approve", "reject", "cancel", "quote", "kill_switch"]
MAX_REQUESTS = 1000


class CreateAccount(PaperModel):
    name: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")]
    initial_cash: Cash
    costs: Costs = Costs()


class RequestKey(PaperModel):
    idempotency_key: Key = Field(repr=False)


class ProposalRequest(RequestKey):
    symbol: Symbol
    side: Side
    quantity: Quantity
    reference_price: Price
    quote_at: AwareDatetime

    @field_validator("quote_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class QuoteRequest(RequestKey):
    symbol: Symbol
    price: Price
    quote_at: AwareDatetime

    @field_validator("quote_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class KillRequest(PaperModel):
    enabled: bool
    idempotency_key: Key | None = Field(default=None, repr=False)


class AccountPage(PaperModel):
    items: tuple[PaperAccount, ...]
    total: int
    page: int
    page_size: int


class SavedResponse(PaperModel):
    account: PaperAccount
    error: PaperCode | None = None


class SavedRequest(PaperModel):
    fingerprint: str
    response_id: str


class PaperDocument(PaperModel):
    account: PaperAccount
    requests: dict[str, SavedRequest] = Field(default_factory=dict)


class PaperStore(Protocol):
    def create(self, document: PaperDocument) -> None: ...
    def get(self, account_id: str) -> PaperDocument: ...
    def identities(self) -> list[str]: ...
    def save_response(self, response: SavedResponse) -> str: ...
    def get_response(self, response_id: str) -> SavedResponse: ...
    def transact(
        self, account_id: str, operation: Callable[[PaperDocument], PaperDocument]
    ) -> PaperDocument: ...


def fingerprint(operation: Operation, target: str, body: PaperModel) -> str:
    def normalized(value: object) -> object:
        if isinstance(value, Decimal):
            return format(value.normalize(), "f")
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if isinstance(value, dict):
            return {k: normalized(v) for k, v in value.items()}
        return value

    payload = normalized(body.model_dump(exclude={"idempotency_key"}))
    return hashlib.sha256(
        json.dumps([operation, target, payload], sort_keys=True).encode()
    ).hexdigest()


class PaperService:
    def __init__(self, store: PaperStore, *, enabled: bool = True) -> None:
        """Accept the persistence port; API composition chooses the adapter."""
        self.store = store
        self.enabled = enabled

    def check_enabled(self) -> None:
        if not self.enabled:
            raise PaperRuleError("PAPER_DISABLED")

    def create(self, body: CreateAccount) -> PaperAccount:
        self.check_enabled()
        account = PaperAccount(
            account_id=f"paper_{uuid4().hex}",
            name=body.name,
            initial_cash=body.initial_cash,
            cash=body.initial_cash,
            costs=body.costs,
        )
        account = audit(
            account, AuditEvent(sequence=1, at=datetime.now(UTC), kind="account_created")
        )
        self.store.create(PaperDocument(account=account))
        return account

    def get(self, identity: str) -> PaperAccount:
        self.check_enabled()
        return self.store.get(identity).account

    def list(self, page: int = 1, page_size: int = 25) -> AccountPage:
        self.check_enabled()
        identities = self.store.identities()
        return AccountPage(
            items=tuple(self.get(i) for i in identities[(page - 1) * page_size : page * page_size]),
            total=len(identities),
            page=page,
            page_size=page_size,
        )

    def reconciliation(self, identity: str) -> Reconciliation:
        return reconcile(self.get(identity))

    def mutate(
        self,
        identity: str,
        operation: Operation,
        body: ProposalRequest | QuoteRequest | RequestKey | KillRequest,
        order_id: str = "",
    ) -> PaperAccount:
        self.check_enabled()
        raw_key = body.idempotency_key
        key = hashlib.sha256(raw_key.encode()).hexdigest() if raw_key else None
        binding = fingerprint(operation, f"{identity}/{order_id}", body)
        response: SavedResponse | None = None

        def transaction(document: PaperDocument) -> PaperDocument:
            nonlocal response
            if key and key in document.requests:
                saved = document.requests[key]
                if saved.fingerprint != binding:
                    raise PaperRuleError("IDEMPOTENCY_CONFLICT")
                response = self.store.get_response(saved.response_id)
                return document
            account = document.account
            if len(document.requests) >= MAX_REQUESTS and operation in {
                "proposal",
                "approve",
                "quote",
            }:
                raise PaperRuleError("CAPACITY_LIMIT")
            at = datetime.now(UTC)
            error: PaperCode | None = None
            kind: Literal[
                "proposal_created",
                "approved_paper_fill",
                "rejected",
                "cancelled",
                "risk_rejected",
                "quote_marked",
                "kill_switch",
                "request_denied",
            ]
            order = next((o for o in account.orders if o.order_id == order_id), None)
            try:
                account, kind = self.transition(account, operation, body, order, at)
                if kind == "proposal_created":
                    order = account.orders[-1]
            except PaperRuleError as exc:
                error = exc.code
                kind = "request_denied"
                if (
                    order
                    and order.state == "pending_approval"
                    and error in {"INSUFFICIENT_CASH", "INSUFFICIENT_POSITION", "NOTIONAL_LIMIT"}
                ):
                    account = set_order(
                        account,
                        order.model_copy(update={"state": "risk_rejected", "reason": error}),
                    )
                    kind = "risk_rejected"
            account = audit(
                account,
                AuditEvent(
                    sequence=len(account.audit) + 1,
                    at=at,
                    kind=kind,
                    order_id=order.order_id if order else None,
                    code=error,
                ),
            )
            response = SavedResponse(account=account, error=error)
            requests = document.requests
            if key:
                response_id = self.store.save_response(response)
                requests = {
                    **requests,
                    key: SavedRequest(fingerprint=binding, response_id=response_id),
                }
            return PaperDocument(account=account, requests=requests)

        self.store.transact(identity, transaction)
        assert response is not None  # noqa: S101
        if response.error:
            raise PaperRuleError(response.error)
        return response.account

    @staticmethod
    def transition(
        account: PaperAccount,
        operation: Operation,
        body: ProposalRequest | QuoteRequest | RequestKey | KillRequest,
        order: PaperOrder | None,
        at: datetime,
    ) -> tuple[
        PaperAccount,
        Literal[
            "proposal_created",
            "approved_paper_fill",
            "rejected",
            "cancelled",
            "quote_marked",
            "kill_switch",
        ],
    ]:
        if operation == "proposal" and isinstance(body, ProposalRequest):
            order = PaperOrder(
                order_id=f"paper_order_{uuid4().hex}",
                created_at=at,
                **body.model_dump(exclude={"idempotency_key"}),
            )
            return propose(account, order), "proposal_created"
        if operation == "quote" and isinstance(body, QuoteRequest):
            return mark_quote(
                account, Quote(**body.model_dump(exclude={"idempotency_key"}))
            ), "quote_marked"
        if operation == "kill_switch" and isinstance(body, KillRequest):
            return account.model_copy(update={"kill_switch": body.enabled}), "kill_switch"
        if order is None:
            raise PaperRuleError("NOT_FOUND")
        if operation == "approve":
            return approve(account, order, at), "approved_paper_fill"
        if order.state != "pending_approval":
            raise PaperRuleError("INVALID_TRANSITION")
        if operation == "reject":
            return set_order(account, order.model_copy(update={"state": "rejected"})), "rejected"
        if operation == "cancel":
            return set_order(account, order.model_copy(update={"state": "cancelled"})), "cancelled"
        raise PaperRuleError("INVALID_TRANSITION")
