"""Translate the exception hierarchy into structured HTTP responses.

Every :class:`AuroraError` becomes a JSON body (``code``/``message``/``details``)
with an appropriate status code. Nothing leaks a stack trace to the client.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aurora.app.core.exceptions import AuroraError
from aurora.app.core.logging import get_logger

_logger = get_logger("api")

# Error code -> HTTP status.
_STATUS: dict[str, int] = {
    "validation_error": 400,
    "configuration_error": 400,
    "tool_error": 400,
    "permission_denied": 403,
    "registry_error": 404,
    "router_error": 409,
    "confirmation_required": 409,
    "transcription_error": 400,
    "provider_error": 502,
    "provider_request_error": 502,
    "provider_response_error": 502,
}


def status_for(exc: AuroraError) -> int:
    """Map an error to its HTTP status (500 for unmapped errors)."""
    return _STATUS.get(exc.code, 500)


def install_error_handlers(app: FastAPI) -> None:
    """Register the structured handler for all AURORA errors."""

    @app.exception_handler(AuroraError)
    async def _handle(_: Request, exc: AuroraError) -> JSONResponse:
        status = status_for(exc)
        if status >= 500:
            _logger.error("unhandled_error", extra={"code": exc.code})
        return JSONResponse(status_code=status, content=exc.to_dict())
