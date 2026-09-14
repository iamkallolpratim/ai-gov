"""Audit log access. Admin only, in both authentication modes."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.api.envelope import EnvelopeRoute
from app.core.exceptions import NotFoundError
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogFilters, AuditLogRead, audit_filters
from app.schemas.common import ErrorResponse, Page, PaginationParams, build_page, pagination_params

router = APIRouter(prefix="/audit-logs", tags=["audit"], route_class=EnvelopeRoute)

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


@router.get(
    "",
    response_model=Page[AuditLogRead],
    summary="Search the audit trail (admin only)",
    responses=ERRORS,
)
def list_audit_logs(
    db: DbSession,
    _: AdminUser,
    filters: Annotated[AuditLogFilters, Depends(audit_filters)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[AuditLogRead]:
    """Immutable record of every mutating action, newest first.

    Entries with `actor_type=system` were taken while the server was running with
    authentication disabled.
    """
    stmt = select(AuditLog)
    if filters.resource_type:
        stmt = stmt.where(AuditLog.resource_type == filters.resource_type)
    if filters.resource_id:
        stmt = stmt.where(AuditLog.resource_id == filters.resource_id)
    if filters.action:
        stmt = stmt.where(AuditLog.action == filters.action)
    if filters.actor_id:
        stmt = stmt.where(AuditLog.actor_id == filters.actor_id)
    if filters.actor_type:
        stmt = stmt.where(AuditLog.actor_type == filters.actor_type)
    if filters.request_id:
        stmt = stmt.where(AuditLog.request_id == filters.request_id)
    if filters.since:
        stmt = stmt.where(AuditLog.created_at >= filters.since)
    if filters.until:
        stmt = stmt.where(AuditLog.created_at <= filters.until)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(AuditLog.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
        .scalars()
        .all()
    )
    return Page[AuditLogRead].model_validate(
        build_page([AuditLogRead.model_validate(r) for r in rows], total, pagination)
    )


@router.get(
    "/{log_id}",
    response_model=AuditLogRead,
    summary="Fetch one audit entry (admin only)",
    responses=ERRORS,
)
def get_audit_log(log_id: uuid.UUID, db: DbSession, _: AdminUser) -> AuditLogRead:
    entry = db.get(AuditLog, log_id)
    if entry is None:
        raise NotFoundError(f"Audit log {log_id} not found.")
    return AuditLogRead.model_validate(entry)
