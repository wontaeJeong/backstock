"""Bounded filesystem research adapter. No broker or credentials are involved."""

from collections.abc import Callable, Coroutine
from functools import partial
from pathlib import Path
from typing import Annotated, Any, ParamSpec, TypeVar

import anyio
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute

from packages.application.research_analysis import Analysis, analyze, export_csv
from packages.application.research_comparison import (
    BenchmarkComparison,
    BenchmarkRequest,
    CompareRequest,
    Comparison,
    ResearchComparison,
)
from packages.application.research_experiment_models import (
    Experiment,
    GridRequest,
    PortfolioExperiment,
    PortfolioRequest,
    WalkForwardRequest,
)
from packages.application.research_experiments import ResearchExperiments
from packages.application.research_library import (
    ArchiveRequest,
    ArchiveState,
    LibraryKind,
    LibraryPage,
    ResearchLibrary,
    SaveStrategy,
    StrategyRecord,
)
from packages.application.research_outcomes import (
    BarPage,
    PortfolioAnalysis,
    portfolio_analysis,
    preview_bars,
)
from packages.application.research_store import ResearchIntegrityError
from packages.application.simulations import SimulationService
from packages.market_data.errors import MarketDataError
from packages.market_data.snapshots import SnapshotIntegrityError

P = ParamSpec("P")
T = TypeVar("T")
MAX_RESEARCH_BODY = 65536


class BoundedResearchRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            if request.method == "POST":
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > MAX_RESEARCH_BODY:
                        raise HTTPException(status_code=413, detail="research body exceeds 64 KiB")
                request._body = bytes(body)  # noqa: SLF001
            return await original(request)

        return handler


def build_research_router(root: Path, simulations: SimulationService) -> APIRouter:  # noqa: C901
    router = APIRouter(prefix="/research", tags=["research"], route_class=BoundedResearchRoute)
    library = ResearchLibrary(root, simulations)
    comparison = ResearchComparison(root, simulations)
    experiments = ResearchExperiments(root, simulations)
    limiter = anyio.CapacityLimiter(2)

    async def call(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await anyio.to_thread.run_sync(
                partial(function, *args, **kwargs), limiter=limiter
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="research artifact not found") from error
        except (ResearchIntegrityError, SnapshotIntegrityError) as error:
            raise HTTPException(
                status_code=409, detail="research artifact integrity failure"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)[:500]) from error
        except MarketDataError as error:
            raise HTTPException(
                status_code=502, detail="provider unavailable; no fallback"
            ) from error

    @router.get("/library/{kind}")
    async def list_library(
        kind: LibraryKind,
        *,
        q: Annotated[str, Query(max_length=200)] = "",
        page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 25,
        archived: bool = False,
    ) -> LibraryPage:
        return await call(
            library.list, kind, q=q, page=page, page_size=page_size, archived=archived
        )

    @router.post("/library/strategies", status_code=201)
    async def save_strategy(body: SaveStrategy) -> StrategyRecord:
        return await call(library.save_strategy, body)

    @router.get("/library/strategies/{identity}")
    async def get_strategy(identity: str) -> StrategyRecord:
        result = await call(library.get, "strategies", identity)
        if not isinstance(result, StrategyRecord):
            raise HTTPException(status_code=404)
        return result

    @router.post("/library/{kind}/{identity}/archive")
    async def archive(kind: LibraryKind, identity: str, body: ArchiveRequest) -> ArchiveState:
        return await call(library.archive, kind, identity, body)

    @router.get("/runs/{run_id}/analysis")
    async def analysis(run_id: str) -> Analysis:
        def operation() -> Analysis:
            return analyze(comparison.run(run_id))

        return await call(operation)

    @router.get("/datasets/{identity}/bars")
    async def bars(
        identity: str,
        page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=1000)] = 250,
    ) -> BarPage:
        return await call(preview_bars, root, identity, page, page_size)

    @router.get("/experiments/{identity}/analysis")
    async def aggregate_analysis(identity: str) -> PortfolioAnalysis:
        def operation() -> PortfolioAnalysis:
            artifact = experiments.get(identity)
            if not isinstance(artifact, PortfolioExperiment):
                raise HTTPException(
                    status_code=422, detail="portfolio analysis requires portfolio experiment"
                )
            return portfolio_analysis(artifact)

        return await call(operation)

    @router.get("/runs/{run_id}/export.csv", response_class=Response)
    async def csv_export(
        run_id: str, kind: Annotated[str, Query(pattern="^(fills|equity|orders)$")] = "fills"
    ) -> Response:
        def operation() -> str:
            from typing import Literal, cast  # noqa: PLC0415

            return export_csv(
                comparison.run(run_id), cast("Literal['fills', 'equity', 'orders']", kind)
            )

        content = await call(operation)
        return Response(
            content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{run_id}-{kind}.csv"'},
        )

    @router.post("/compare")
    async def compare(body: CompareRequest) -> Comparison:
        return await call(comparison.compare, body)

    @router.post("/benchmark")
    async def benchmark(body: BenchmarkRequest) -> BenchmarkComparison:
        return await call(comparison.benchmark, body)

    @router.post("/experiments/grid", status_code=201)
    async def grid(body: GridRequest) -> Experiment:
        return await call(experiments.grid, body)

    @router.post("/experiments/walk-forward", status_code=201)
    async def walk_forward(body: WalkForwardRequest) -> Experiment:
        return await call(experiments.walk_forward, body)

    @router.post("/experiments/portfolio", status_code=201)
    async def portfolio(body: PortfolioRequest) -> Experiment:
        return await call(experiments.portfolio, body)

    @router.get("/experiments/{identity}")
    async def experiment(identity: str) -> Experiment:
        return await call(experiments.get, identity)

    return router
