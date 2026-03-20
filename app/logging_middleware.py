# app/logging_middleware.py
r"""Request tracing and logging middleware for Step 7 observability."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for request_id accessible in request scope
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return current request_id from context."""
    return request_id_ctx.get() or ""


def _generate_trace_id() -> str:
    return str(uuid.uuid4())


logger = logging.getLogger("app")


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Adds request_id/trace_id to headers and logs request/response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id") or _generate_trace_id()
        request_id_ctx.set(trace_id)

        start = time.perf_counter()
        method = request.method
        path = request.url.path

        logger.info(
            "request_start",
            extra={
                "request_id": trace_id,
                "method": method,
                "path": path,
            },
        )

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "request_complete",
            extra={
                "request_id": trace_id,
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # Propagate trace_id in response headers for client correlation
        response.headers["X-Request-Id"] = trace_id
        response.headers["X-Trace-Id"] = trace_id

        return response
