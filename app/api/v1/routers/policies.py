"""Policy management (admin) and batch evaluation (risk officers and admins)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession, RiskOfficerUser
from app.api.envelope import EnvelopeRoute
from app.models.ai_system import AISystem
from app.models.enums import PolicySeverity
from app.schemas.common import ErrorResponse, Page, PaginationParams, build_page, pagination_params
from app.schemas.policy import (
    BatchPolicyCheckRequest,
    BatchPolicyCheckResponse,
    PolicyCheckRead,
    PolicyCheckRunResponse,
    PolicyCreate,
    PolicyRead,
    PolicyUpdate,
)
from app.services.cache import cache_invalidate
from app.services.policy import PolicyService

router = APIRouter(prefix="/policies", tags=["policies"], route_class=EnvelopeRoute)

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


@router.get(
    "",
    response_model=Page[PolicyRead],
    summary="List policies",
    responses={401: {"model": ErrorResponse}},
)
def list_policies(
    db: DbSession,
    _: CurrentUser,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    jurisdiction: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    severity: Annotated[PolicySeverity | None, Query()] = None,
) -> Page[PolicyRead]:
    policies, total = PolicyService(db).list_policies(
        jurisdiction_code=jurisdiction,
        is_active=is_active,
        severity=severity,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return Page[PolicyRead].model_validate(
        build_page([PolicyRead.model_validate(p) for p in policies], total, pagination)
    )


@router.post(
    "",
    response_model=PolicyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a policy (admin only)",
    responses={**ERRORS, 409: {"model": ErrorResponse}},
)
def create_policy(payload: PolicyCreate, db: DbSession, admin: AdminUser) -> PolicyRead:
    return PolicyRead.model_validate(PolicyService(db).create(payload, actor=admin))


@router.get("/{policy_id}", response_model=PolicyRead, summary="Fetch one policy", responses=ERRORS)
def get_policy(policy_id: uuid.UUID, db: DbSession, _: CurrentUser) -> PolicyRead:
    return PolicyRead.model_validate(PolicyService(db).get(policy_id))


@router.patch(
    "/{policy_id}",
    response_model=PolicyRead,
    summary="Update a policy (admin only)",
    responses=ERRORS,
)
def update_policy(
    policy_id: uuid.UUID, payload: PolicyUpdate, db: DbSession, admin: AdminUser
) -> PolicyRead:
    return PolicyRead.model_validate(PolicyService(db).update(policy_id, payload, actor=admin))


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a policy (admin only, soft delete)",
    responses=ERRORS,
)
def delete_policy(policy_id: uuid.UUID, db: DbSession, admin: AdminUser) -> Response:
    PolicyService(db).soft_delete(policy_id, actor=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sync-opa",
    summary="Push all active Rego policies into OPA (admin only)",
    responses=ERRORS,
)
def sync_opa(db: DbSession, _: AdminUser) -> dict[str, int]:
    """Push shared Rego libraries and all active policies into OPA."""
    return PolicyService(db).sync_all_to_opa()


@router.post(
    "/batch-check",
    response_model=BatchPolicyCheckResponse,
    summary="Evaluate many systems in one call",
    responses=ERRORS,
)
def batch_check(
    payload: BatchPolicyCheckRequest, db: DbSession, user: RiskOfficerUser
) -> BatchPolicyCheckResponse:
    systems = list(
        db.execute(
            select(AISystem).where(
                AISystem.id.in_(payload.ai_system_ids), AISystem.is_deleted.is_(False)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    service = PolicyService(db)
    results = service.evaluate_batch(
        systems,
        jurisdiction_codes=payload.jurisdictions,
        policy_keys=payload.policy_keys,
        reclassify=payload.reclassify,
        actor=user,
    )
    cache_invalidate("dashboard:*")
    now = datetime.now(UTC)
    return BatchPolicyCheckResponse(
        results=[
            PolicyCheckRunResponse(
                ai_system_id=system_id,
                summary=service.summarize(checks),  # type: ignore[arg-type]
                checks=[PolicyCheckRead.model_validate(c) for c in checks],
                checked_at=now,
            )
            for system_id, checks in results.items()
        ]
    )
