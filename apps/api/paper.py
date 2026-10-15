"""Bounded paper-only HTTP adapter. Concrete storage is wired in app composition."""

from collections.abc import Callable
from functools import partial
from typing import Annotated, Literal, ParamSpec, TypeVar

import anyio
from fastapi import APIRouter, Query

from apps.api.research import BoundedResearchRoute
from packages.application.paper import (
    AccountPage,
    CreateAccount,
    KillRequest,
    PaperService,
    ProposalRequest,
    QuoteRequest,
    RequestKey,
)
from packages.domain.paper import PaperAccount, PaperCode, PaperRuleError, Reconciliation

P = ParamSpec("P")
T = TypeVar("T")


def build_paper_router(service: PaperService) -> APIRouter:  # noqa: C901
    router = APIRouter(prefix="/paper/accounts", tags=["paper"], route_class=BoundedResearchRoute)
    limiter = anyio.CapacityLimiter(2)

    async def call(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await anyio.to_thread.run_sync(
                partial(function, *args, **kwargs), limiter=limiter
            )
        except OSError as exc:
            code: PaperCode = "PAPER_STORAGE_ERROR"
            raise PaperRuleError(code) from exc

    @router.post("", status_code=201)
    async def create(body: CreateAccount) -> PaperAccount:
        return await call(service.create, body)

    @router.get("")
    async def listing(
        page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> AccountPage:
        return await call(service.list, page, page_size)

    @router.get("/{identity}")
    async def get(identity: str) -> PaperAccount:
        return await call(service.get, identity)

    @router.get("/{identity}/reconciliation")
    async def reconciliation(identity: str) -> Reconciliation:
        return await call(service.reconciliation, identity)

    @router.post("/{identity}/proposals")
    async def proposal(identity: str, body: ProposalRequest) -> PaperAccount:
        return await call(service.mutate, identity, "proposal", body)

    @router.post("/{identity}/quotes")
    async def quote(identity: str, body: QuoteRequest) -> PaperAccount:
        return await call(service.mutate, identity, "quote", body)

    @router.post("/{identity}/kill-switch")
    async def kill(identity: str, body: KillRequest) -> PaperAccount:
        return await call(service.mutate, identity, "kill_switch", body)

    @router.post("/{identity}/orders/{order_id}/{action}")
    async def order_action(
        identity: str,
        order_id: str,
        action: Literal["approve", "reject", "cancel"],
        body: RequestKey,
    ) -> PaperAccount:
        return await call(service.mutate, identity, action, body, order_id)

    return router
