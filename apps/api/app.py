from tempfile import TemporaryFile

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.datasets import build_dataset_router
from apps.api.middleware import RequestContextMiddleware, request_id_context
from apps.api.schemas import ErrorResponse, HealthResponse
from apps.api.simulations import build_simulation_router, source_revision
from apps.api.strategies import build_strategy_router
from packages.application.datasets import (
    DatasetInvalidError,
    DatasetSnapshotService,
    SnapshotNotFoundError,
)
from packages.application.simulations import SimulationService
from packages.market_data.snapshots import FileSnapshotStore
from packages.shared.logging import configure_logging
from packages.shared.settings import Settings, get_settings
from packages.strategy.validation import StrategyValidationError


async def live() -> HealthResponse:
    return HealthResponse(status="live")


async def api_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    match exc:
        case StarletteHTTPException(status_code=status_code):
            error = ErrorResponse(
                code="NOT_FOUND" if status_code == status.HTTP_404_NOT_FOUND else "HTTP_ERROR",
                message=(
                    "Resource not found"
                    if status_code == status.HTTP_404_NOT_FOUND
                    else "HTTP request failed"
                ),
                request_id=request_id_context.get(),
            )
            return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))
        case RequestValidationError():
            error = ErrorResponse(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={},
                request_id=request_id_context.get(),
            )
            return JSONResponse(status_code=422, content=error.model_dump(mode="json"))
        case DatasetInvalidError(report=report):
            error = ErrorResponse(
                code="DATASET_INVALID",
                message="Dataset validation failed",
                details={
                    "issues": [
                        {
                            "code": issue.code.value,
                            "severity": issue.severity.value,
                            "message": issue.message,
                        }
                        for issue in report.issues
                    ]
                },
                request_id=request_id_context.get(),
            )
            return JSONResponse(status_code=422, content=error.model_dump(mode="json"))
        case SnapshotNotFoundError():
            error = ErrorResponse(
                code="NOT_FOUND",
                message="Dataset snapshot not found",
                request_id=request_id_context.get(),
            )
            return JSONResponse(status_code=404, content=error.model_dump(mode="json"))
        case StrategyValidationError(issues=issues):
            error = ErrorResponse(
                code="STRATEGY_INVALID",
                message="Strategy definition failed validation",
                details={
                    "issues": [{"path": issue.path, "message": issue.message} for issue in issues]
                },
                request_id=request_id_context.get(),
            )
            return JSONResponse(status_code=422, content=error.model_dump(mode="json"))
        case unknown:
            raise unknown


def create_app(
    settings: Settings | None = None,
    *,
    dataset_service: DatasetSnapshotService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    app = FastAPI(
        title="Stock Strategy Lab API",
        version="0.1.0",
    )
    app.add_middleware(RequestContextMiddleware)

    def ready() -> HealthResponse | JSONResponse:
        try:
            resolved_settings.data_storage_path.mkdir(parents=True, exist_ok=True)
            with TemporaryFile(dir=resolved_settings.data_storage_path) as probe:
                _ = probe.write(b"ready")
                probe.flush()
        except OSError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return HealthResponse(status="ready")

    app.add_api_route("/health/live", live, methods=["GET"], tags=["health"])
    app.add_api_route(
        "/health/ready", ready, methods=["GET"], tags=["health"], response_model=HealthResponse
    )
    resolved_dataset_service = dataset_service or DatasetSnapshotService(
        FileSnapshotStore(resolved_settings.data_storage_path / "published")
    )
    app.include_router(build_dataset_router(resolved_dataset_service, resolved_settings))
    app.include_router(build_strategy_router())
    app.include_router(
        build_simulation_router(
            SimulationService(resolved_settings.data_storage_path, code_revision=source_revision())
        )
    )
    app.add_exception_handler(StarletteHTTPException, api_exception_handler)
    app.add_exception_handler(RequestValidationError, api_exception_handler)
    app.add_exception_handler(DatasetInvalidError, api_exception_handler)
    app.add_exception_handler(SnapshotNotFoundError, api_exception_handler)
    app.add_exception_handler(StrategyValidationError, api_exception_handler)
    return app


app = create_app()
