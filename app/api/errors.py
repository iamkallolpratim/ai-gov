"""Exception handlers producing the standard error envelope."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import get_request_id
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("api.errors")

#: Starlette raises bare HTTPExceptions in a few places; map them onto our vocabulary.
HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details if details is not None else {},
                "request_id": get_request_id(),
            },
        },
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", code=exc.code, message=exc.message)
        return error_response(
            exc.status_code,
            exc.code,
            exc.message,
            exc.details,
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"errors": _jsonable_errors(exc.errors())},
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return error_response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Rate limit exceeded. Slow down and retry.",
            {"limit": str(exc.detail)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
        return error_response(
            exc.status_code,
            code,
            str(exc.detail),
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Never leak an internal message or stack trace to the client.
        logger.exception("unhandled_exception", error=str(exc))
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
        )


def _jsonable_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    """Validation errors can carry exception objects, which are not JSON-serialisable."""
    cleaned: list[dict[str, Any]] = []
    for err in errors:
        item = {k: v for k, v in err.items() if k != "ctx"}
        if ctx := err.get("ctx"):
            item["ctx"] = {k: str(v) for k, v in ctx.items()}
        cleaned.append(item)
    return cleaned
