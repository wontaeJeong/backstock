import logging
from contextvars import ContextVar
from typing import Final, override
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from packages.shared.logging import request_log_payload

REQUEST_ID_HEADER: Final = "X-Request-ID"
request_id_context: ContextVar[str] = ContextVar("request_id", default="unavailable")
request_logger = logging.getLogger("backstock.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid4()))
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            if not request.url.path.startswith("/health/"):
                request_logger.info(
                    request_log_payload(
                        request_id=request_id,
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                    )
                )
            return response
        finally:
            request_id_context.reset(token)
