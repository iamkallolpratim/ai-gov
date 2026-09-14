"""SlowAPI rate limiter, backed by Redis when available."""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _identify(request: Request) -> str:
    """Rate-limit per authenticated user where possible, else per client IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return f"token:{hash(auth[7:])}"
    return get_remote_address(request)


def login_limit() -> str:
    return settings.RATE_LIMIT_LOGIN


def evidence_limit() -> str:
    return settings.RATE_LIMIT_EVIDENCE


def policy_check_limit() -> str:
    return settings.RATE_LIMIT_POLICY_CHECK


# Limits are passed as callables so they are read per request: a test (or a reload) can
# change them without the decorator having captured a stale string at import time.
limiter = Limiter(
    key_func=_identify,
    default_limits=[settings.RATE_LIMIT_DEFAULT] if settings.RATE_LIMIT_ENABLED else [],
    storage_uri=settings.rate_limit_storage_uri,
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,
)
