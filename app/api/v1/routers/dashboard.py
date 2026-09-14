"""Dashboard aggregates."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.envelope import EnvelopeRoute
from app.schemas.common import ErrorResponse
from app.schemas.dashboard import (
    DashboardSummary,
    JurisdictionDashboard,
    PendingReview,
    RecentFailure,
)
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"], route_class=EnvelopeRoute)

ERRORS: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}}


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Portfolio-wide compliance summary",
    responses=ERRORS,
)
def summary(
    db: DbSession,
    _: CurrentUser,
    refresh: Annotated[bool, Query(description="Bypass the cache")] = False,
) -> DashboardSummary:
    return DashboardSummary.model_validate(DashboardService(db).summary(use_cache=not refresh))


@router.get(
    "/by-jurisdiction",
    response_model=JurisdictionDashboard,
    summary="Compliance status broken down by jurisdiction",
    responses=ERRORS,
)
def by_jurisdiction(
    db: DbSession,
    _: CurrentUser,
    refresh: Annotated[bool, Query()] = False,
) -> JurisdictionDashboard:
    return JurisdictionDashboard.model_validate(
        DashboardService(db).by_jurisdiction(use_cache=not refresh)
    )


@router.get(
    "/recent-failures",
    response_model=list[RecentFailure],
    summary="Most recent failing policy checks",
    responses=ERRORS,
)
def recent_failures(
    db: DbSession,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RecentFailure]:
    return [
        RecentFailure.model_validate(r) for r in DashboardService(db).recent_failures(limit=limit)
    ]


@router.get(
    "/pending-reviews",
    response_model=list[PendingReview],
    summary="Systems awaiting (re)classification",
    responses=ERRORS,
)
def pending_reviews(
    db: DbSession,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PendingReview]:
    return [
        PendingReview.model_validate(r) for r in DashboardService(db).pending_reviews(limit=limit)
    ]
