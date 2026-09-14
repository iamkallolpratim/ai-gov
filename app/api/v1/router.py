"""Aggregate router for API v1.

Each sub-router sets `route_class=EnvelopeRoute` itself: FastAPI's `include_router`
preserves the route class a route was created with, so setting it here would have no
effect on routes defined elsewhere.
"""

from fastapi import APIRouter

from app.api.v1.routers import audit, auth, dashboard, jurisdictions, policies, systems

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(systems.router)
api_router.include_router(policies.router)
api_router.include_router(jurisdictions.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
