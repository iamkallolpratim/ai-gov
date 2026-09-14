"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from slowapi.middleware import SlowAPIMiddleware

from app.api.envelope import envelope_openapi
from app.api.errors import register_exception_handlers
from app.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.api.rate_limit import limiter
from app.api.v1.router import api_router
from app.api.v1.routers import health
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

DESCRIPTION = """
Backend for the **AI Governance Console** — multi-jurisdictional AI compliance.

* **Inventory** of AI systems with full metadata version history
* **Jurisdiction detection** and **risk classification** (global baseline + regional overlays)
* **Policy-as-code** checks evaluated through Open Policy Agent
* **Evidence packages** (PDF + JSON) generated asynchronously and stored in S3
* **Dashboards** aggregating compliance by jurisdiction and risk tier

### Response format

Every response under `/api/v1` uses the same envelope:

```json
{"success": true, "data": { ... }}
```

```json
{"success": false, "error": {"code": "UNAUTHORIZED", "message": "...", "details": {}}}
```

### Authentication

Authenticate with `POST /api/v1/auth/login`, then send `Authorization: Bearer <token>`.
Roles: `admin` (everything), `risk_officer` (inventory + assessments), `viewer` (read-only).

Servers may run with `AUTH_DISABLED=true`, in which case no token is required and every
request is attributed to a system principal with the admin role. Check `GET /api/v1/auth/me`
to see which mode a deployment is in.
"""


def _log_auth_mode() -> None:
    if not settings.AUTH_DISABLED:
        logger.info("auth_mode", auth_enabled=True, environment=settings.ENVIRONMENT)
        return

    # Deliberately loud, and repeated per line so it survives log aggregation.
    banner = "!" * 78
    for line in (
        banner,
        "!! AUTHENTICATION IS DISABLED (AUTH_DISABLED=true).",
        "!! Every request is served with FULL ADMIN PRIVILEGES and no credentials.",
        "!! Anyone who can reach this port can read and modify all compliance data.",
        "!! Only run this way on a trusted private network you fully control.",
        banner,
    ):
        logger.warning(
            "auth_disabled_insecure_mode",
            message=line,
            environment=settings.ENVIRONMENT,
        )
    if settings.ENVIRONMENT == "production":
        logger.error(
            "auth_disabled_in_production",
            message=(
                "AUTH_DISABLED is set in a production environment. This is almost "
                "certainly a misconfiguration."
            ),
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("app_starting", environment=settings.ENVIRONMENT, app=settings.APP_NAME)
    _log_auth_mode()
    yield
    logger.info("app_stopping")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.APP_NAME,
        description=DESCRIPTION,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={"name": "AI Governance Platform Team"},
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0",
        },
    )

    app.state.limiter = limiter

    # Middleware runs bottom-up on the way in: CORS is outermost so preflight requests
    # are answered before anything else, and the request context is established before
    # any handler or rate-limit check runs.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Correlation-ID"],
    )

    register_exception_handlers(app)

    # Ops endpoints stay unwrapped: probes and Prometheus expect their own formats.
    app.include_router(health.router)

    # Everything under /api/v1 is wrapped in the success envelope (see app/api/v1/router.py).
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    app.openapi = _openapi(app)  # type: ignore[method-assign]
    return app


def _openapi(app: FastAPI) -> Any:
    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            license_info=app.license_info,
        )
        schema = envelope_openapi(schema)
        schema["info"]["x-auth-disabled"] = settings.AUTH_DISABLED
        app.openapi_schema = schema
        return schema

    return openapi


app = create_app()
