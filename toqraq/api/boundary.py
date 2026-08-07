"""FastAPI trace, validation, and failure presenter."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import Response

from ..contracts.errors import error_envelope
from ..contracts.validation import invalid_request
from ..core.errors import (
    ErrorCategory,
    ToqraqError,
    UnexpectedError,
)
from ..core.failure_diagnostics import failure_diagnostic
from ..core.trace import trace_scope

logger = logging.getLogger(__name__)

_TRACE_HEADER = "x-trace-id"
_CATEGORY_STATUS: dict[ErrorCategory, int] = {
    ErrorCategory.INVALID: 400,
    ErrorCategory.UNAUTHENTICATED: 401,
    ErrorCategory.FORBIDDEN: 403,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.CONFLICT: 409,
    ErrorCategory.UNAVAILABLE: 424,
    ErrorCategory.TIMEOUT: 504,
    ErrorCategory.UPSTREAM: 502,
    ErrorCategory.INTERNAL: 500,
}


class ToqraqRoute(APIRoute):
    """Own one trace and one safe error conversion for an HTTP route."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Wrap FastAPI validation, endpoint execution, and serialization."""
        route_handler = super().get_route_handler()

        async def traced_handler(request: Request) -> Response:
            candidate = request.headers.get(_TRACE_HEADER)
            with trace_scope(candidate):
                try:
                    return await route_handler(request)
                except RequestValidationError as exc:
                    return error_response(invalid_request(exc.errors()))
                except ToqraqError as exc:
                    return error_response(exc)
                except Exception as exc:
                    error = UnexpectedError(cause=exc)
                    _log_unexpected(error, exc)
                    return error_response(error)

        return traced_handler


def error_response(error: ToqraqError) -> JSONResponse:
    """Serialize one application failure with category-based HTTP status."""
    envelope = error_envelope(error)
    return JSONResponse(
        status_code=status_for(error.category),
        content=envelope.model_dump(mode="json"),
    )


def status_for(category: ErrorCategory) -> int:
    """Map every closed error category to its HTTP status."""
    return _CATEGORY_STATUS[category]


def _log_unexpected(error: UnexpectedError, exception: BaseException) -> None:
    """Log only reviewed diagnostic fields for an unexpected HTTP failure."""
    diagnostic = failure_diagnostic(exception)
    logger.error(
        "unexpected HTTP failure trace_id=%s exception_type=%s stack_locations=%s",
        error.trace_id,
        diagnostic.exception_type,
        ",".join(diagnostic.stack_locations),
    )
