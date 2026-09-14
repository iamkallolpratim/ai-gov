"""Liveness, readiness, and Prometheus metrics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.services.cache import ping as redis_ping
from app.services.opa import get_opa_client
from app.services.storage import get_storage

router = APIRouter(tags=["ops"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, Any]:
    """Process is up. Never touches a dependency, so it cannot cascade a restart."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "auth_enabled": settings.auth_enabled,
    }


@router.get("/health/live", summary="Liveness probe (alias)")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe — checks every dependency")
@router.get("/health/ready", summary="Readiness probe (alias)")
def ready(db: DbSession, response: Response) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001 - readiness must never raise
        checks["database"] = False
    checks["redis"] = redis_ping()
    checks["opa"] = get_opa_client().health()
    try:
        checks["storage"] = get_storage().healthy()
    except Exception:  # noqa: BLE001
        checks["storage"] = False

    # Redis, OPA and storage degrade gracefully; only the database is hard-required.
    ok = checks["database"]
    response.status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ok else "not_ready",
        "checks": checks,
        "auth_enabled": settings.auth_enabled,
    }


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
