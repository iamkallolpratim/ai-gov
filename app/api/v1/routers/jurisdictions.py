"""Jurisdiction registry and ad-hoc applicability detection."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.api.envelope import EnvelopeRoute
from app.core.exceptions import ConflictError, NotFoundError
from app.models.jurisdiction import Jurisdiction
from app.schemas.common import ErrorResponse
from app.schemas.jurisdiction import (
    JurisdictionCreate,
    JurisdictionDetectionResult,
    JurisdictionRead,
    JurisdictionUpdate,
)
from app.services.inventory import InventoryService
from app.services.jurisdiction_engine import SystemProfile, load_engine
from app.services.jurisdiction_mapping import assessment_to_result

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"], route_class=EnvelopeRoute)

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


@router.get("", response_model=list[JurisdictionRead], summary="List jurisdictions")
def list_jurisdictions(
    db: DbSession,
    _: CurrentUser,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[JurisdictionRead]:
    stmt = select(Jurisdiction)
    if is_active is not None:
        stmt = stmt.where(Jurisdiction.is_active.is_(is_active))
    rows = db.execute(stmt.order_by(Jurisdiction.code)).scalars().all()
    return [JurisdictionRead.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=JurisdictionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a jurisdiction (admin only)",
    responses={**ERRORS, 409: {"model": ErrorResponse}},
)
def create_jurisdiction(
    payload: JurisdictionCreate, db: DbSession, _: AdminUser
) -> JurisdictionRead:
    code = payload.code.upper()
    if db.execute(select(Jurisdiction).where(Jurisdiction.code == code)).scalar_one_or_none():
        raise ConflictError(f"Jurisdiction '{code}' already exists.")
    jur = Jurisdiction(**{**payload.model_dump(), "code": code})
    db.add(jur)
    db.flush()
    return JurisdictionRead.model_validate(jur)


@router.get(
    "/{code}", response_model=JurisdictionRead, summary="Fetch one jurisdiction", responses=ERRORS
)
def get_jurisdiction(code: str, db: DbSession, _: CurrentUser) -> JurisdictionRead:
    jur = db.execute(
        select(Jurisdiction).where(Jurisdiction.code == code.upper())
    ).scalar_one_or_none()
    if jur is None:
        raise NotFoundError(f"Jurisdiction '{code}' not found.")
    return JurisdictionRead.model_validate(jur)


@router.patch(
    "/{code}",
    response_model=JurisdictionRead,
    summary="Update a jurisdiction (admin only)",
    responses=ERRORS,
)
def update_jurisdiction(
    code: str, payload: JurisdictionUpdate, db: DbSession, _: AdminUser
) -> JurisdictionRead:
    jur = db.execute(
        select(Jurisdiction).where(Jurisdiction.code == code.upper())
    ).scalar_one_or_none()
    if jur is None:
        raise NotFoundError(f"Jurisdiction '{code}' not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(jur, field, value)
    db.flush()
    return JurisdictionRead.model_validate(jur)


@router.get(
    "/detect/{system_id}",
    response_model=JurisdictionDetectionResult,
    summary="Detect applicable jurisdictions for a system without persisting",
    responses=ERRORS,
)
def detect_for_system(
    system_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    include_inapplicable: Annotated[
        bool, Query(description="Also return regimes that were evaluated but do not apply")
    ] = True,
) -> JurisdictionDetectionResult:
    """Dry-run the jurisdiction engine. Writes nothing — use `/systems/{id}/classify` to persist."""
    system = InventoryService(db).get(system_id)
    assessment = load_engine(db).evaluate(SystemProfile.from_system(system))
    return assessment_to_result(assessment, system.id, include_inapplicable=include_inapplicable)
