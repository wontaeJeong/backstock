from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.middleware import RequestContextMiddleware, request_id_context
from apps.api.schemas import ErrorResponse, HealthResponse
from packages.shared.logging import configure_logging
from packages.shared.settings import Settings, get_settings


async def live() -> HealthResponse:
    return HealthResponse(status="live")


async def ready() -> HealthResponse:
    return HealthResponse(status="ready")


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
        case unknown:
            raise unknown


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    app = FastAPI(
        title="Stock Strategy Lab API",
        version="0.1.0",
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_api_route("/health/live", live, methods=["GET"], tags=["health"])
    app.add_api_route("/health/ready", ready, methods=["GET"], tags=["health"])
    app.add_exception_handler(StarletteHTTPException, api_exception_handler)
    app.add_exception_handler(RequestValidationError, api_exception_handler)
    return app


app = create_app()
