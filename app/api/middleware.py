"""Request-scoped middleware: request id, client capture, access logs, secure headers."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.context import reset_context, set_client_info, set_request_id
from app.core.logging import get_logger

logger = get_logger("api.access")

REQUEST_ID_HEADER = "X-Request-ID"
#: Previous header name, still accepted on the way in and echoed on the way out.
CORRELATION_ID_HEADER = "X-Correlation-ID"

#: Paths that would otherwise flood the logs with probe traffic.
QUIET_PATHS = frozenset({"/health", "/health/live", "/health/ready", "/ready", "/metrics"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, capture the client fingerprint, and log the outcome."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        reset_context()
        incoming = request.headers.get(REQUEST_ID_HEADER) or request.headers.get(
            CORRELATION_ID_HEADER
        )
        request_id = set_request_id(incoming)
        request.state.request_id = request_id
        # Kept for callers that still read request.state.correlation_id.
        request.state.correlation_id = request_id
        set_client_info(_client_ip(request), request.headers.get("user-agent"))

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[CORRELATION_ID_HEADER] = request_id
        if request.url.path not in QUIET_PATHS:
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        return response


def _client_ip(request: Request) -> str | None:
    """Client address, honouring one layer of reverse proxy.

    `X-Forwarded-For` is caller-controlled, so this value is evidence for an audit trail,
    not an authentication signal. Only trust it when a proxy you control sets it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()[:45]
    return request.client.host if request.client else None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Conservative security headers.

    This service is a JSON API, so the CSP simply forbids everything — nothing here is
    meant to be embedded or to load subresources. The interactive docs are exempt,
    because Swagger UI legitimately loads its own assets and inline bootstrap script.
    """

    DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if not settings.SECURITY_HEADERS_ENABLED:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=(), interest-cohort=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        if request.url.path not in self.DOCS_PATHS:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )

        # Only meaningful over TLS, and actively harmful if sent on plain HTTP in dev.
        if settings.HSTS_MAX_AGE_SECONDS > 0 and request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains",
            )
        return response


# Previous name.
CorrelationIdMiddleware = RequestContextMiddleware
