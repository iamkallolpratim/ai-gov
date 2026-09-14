"""AI system inventory: CRUD, search, versions, classification, policy checks, evidence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import CurrentUser, DbSession, RiskOfficerUser
from app.api.envelope import EnvelopeRoute
from app.api.rate_limit import evidence_limit, limiter, policy_check_limit
from app.core.exceptions import NotFoundError, TaskQueueError
from app.core.logging import get_logger
from app.models.enums import EvidenceStatus, RiskTier
from app.models.evidence import EvidencePackage
from app.schemas.common import ErrorResponse, Page, PaginationParams, build_page, pagination_params
from app.schemas.evidence import (
    EvidenceAcceptedResponse,
    EvidenceGenerateRequest,
    EvidencePackageRead,
)
from app.schemas.policy import PolicyCheckRead, PolicyCheckRequest, PolicyCheckRunResponse
from app.schemas.risk import ClassificationRequest, ClassificationResponse, RiskClassificationRead
from app.schemas.system import (
    AISystemCreate,
    AISystemRead,
    AISystemUpdate,
    SystemFilters,
    SystemVersionRead,
    system_filters,
)
from app.services.cache import cache_invalidate
from app.services.evidence import EvidenceGeneratorService
from app.services.inventory import InventoryService
from app.services.jurisdiction_mapping import assessment_to_result, verdict_to_match
from app.services.policy import PolicyService
from app.services.risk import RiskClassificationService
from app.workers.tasks import generate_evidence_package

logger = get_logger(__name__)

router = APIRouter(prefix="/systems", tags=["systems"], route_class=EnvelopeRoute)

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


def _invalidate_dashboard() -> None:
    cache_invalidate("dashboard:*")


@router.get(
    "",
    response_model=Page[AISystemRead],
    summary="List and search the AI system inventory",
    responses={401: {"model": ErrorResponse}},
)
def list_systems(
    db: DbSession,
    _: CurrentUser,
    filters: Annotated[SystemFilters, Depends(system_filters)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[AISystemRead]:
    items, total = InventoryService(db).list_systems(filters, pagination)
    return Page[AISystemRead].model_validate(
        build_page([AISystemRead.model_validate(i) for i in items], total, pagination)
    )


@router.post(
    "",
    response_model=AISystemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new AI system",
    responses={**ERRORS, 409: {"model": ErrorResponse}},
)
def create_system(payload: AISystemCreate, db: DbSession, user: RiskOfficerUser) -> AISystemRead:
    system = InventoryService(db).create(payload, actor=user)
    _invalidate_dashboard()
    return AISystemRead.model_validate(system)


@router.get(
    "/{system_id}",
    response_model=AISystemRead,
    summary="Fetch one AI system",
    responses=ERRORS,
)
def get_system(system_id: uuid.UUID, db: DbSession, _: CurrentUser) -> AISystemRead:
    return AISystemRead.model_validate(InventoryService(db).get(system_id))


@router.patch(
    "/{system_id}",
    response_model=AISystemRead,
    summary="Update an AI system (creates a new metadata version)",
    responses=ERRORS,
)
def update_system(
    system_id: uuid.UUID, payload: AISystemUpdate, db: DbSession, user: RiskOfficerUser
) -> AISystemRead:
    system = InventoryService(db).update(system_id, payload, actor=user)
    _invalidate_dashboard()
    return AISystemRead.model_validate(system)


@router.delete(
    "/{system_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an AI system",
    responses=ERRORS,
)
def delete_system(system_id: uuid.UUID, db: DbSession, user: RiskOfficerUser) -> Response:
    InventoryService(db).soft_delete(system_id, actor=user)
    _invalidate_dashboard()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{system_id}/restore",
    response_model=AISystemRead,
    summary="Restore a soft-deleted AI system",
    responses=ERRORS,
)
def restore_system(system_id: uuid.UUID, db: DbSession, user: RiskOfficerUser) -> AISystemRead:
    system = InventoryService(db).restore(system_id, actor=user)
    _invalidate_dashboard()
    return AISystemRead.model_validate(system)


@router.get(
    "/{system_id}/versions",
    response_model=list[SystemVersionRead],
    summary="Metadata version history",
    responses=ERRORS,
)
def list_versions(system_id: uuid.UUID, db: DbSession, _: CurrentUser) -> list[SystemVersionRead]:
    return [
        SystemVersionRead.model_validate(v) for v in InventoryService(db).list_versions(system_id)
    ]


# ---------- classification ----------


@router.post(
    "/{system_id}/classify",
    response_model=ClassificationResponse,
    summary="Detect jurisdictions and classify risk",
    responses=ERRORS,
)
def classify_system(
    system_id: uuid.UUID,
    payload: ClassificationRequest,
    db: DbSession,
    user: RiskOfficerUser,
) -> ClassificationResponse:
    inventory = InventoryService(db)
    service = RiskClassificationService(db)
    system = inventory.get(system_id)
    assessment, classifications = service.classify(
        system, jurisdiction_codes=payload.jurisdictions, actor=user
    )
    tier = service.most_restrictive_tier(classifications)
    evaluated_at = datetime.now(UTC)
    _invalidate_dashboard()
    return ClassificationResponse(
        ai_system_id=system.id,
        jurisdictions=assessment_to_result(assessment, system.id, evaluated_at=evaluated_at),
        detected_jurisdictions=[verdict_to_match(v) for v in assessment.applicable],
        classifications=[RiskClassificationRead.model_validate(c) for c in classifications],
        most_restrictive_tier=RiskTier(str(tier)),
        most_restrictive_jurisdiction=assessment.primary,
        evaluated_at=evaluated_at,
    )


@router.get(
    "/{system_id}/classifications",
    response_model=list[RiskClassificationRead],
    summary="Classification history (immutable)",
    responses=ERRORS,
)
def list_classifications(
    system_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    jurisdiction: Annotated[str | None, Query()] = None,
    latest_only: Annotated[bool, Query(description="Only the latest per jurisdiction")] = False,
) -> list[RiskClassificationRead]:
    service = RiskClassificationService(db)
    InventoryService(db).get(system_id, include_deleted=True)
    records = (
        list(service.latest_for_system(system_id).values())
        if latest_only
        else service.history(system_id, jurisdiction_code=jurisdiction)
    )
    return [RiskClassificationRead.model_validate(r) for r in records]


# ---------- policy checks ----------


@router.post(
    "/{system_id}/check-policies",
    response_model=PolicyCheckRunResponse,
    summary="Evaluate the system against applicable policies via OPA",
    responses=ERRORS,
)
@limiter.limit(policy_check_limit)
def check_policies(
    request: Request,
    response: Response,
    system_id: uuid.UUID,
    payload: PolicyCheckRequest,
    db: DbSession,
    user: RiskOfficerUser,
) -> PolicyCheckRunResponse:
    """Evaluate the system against every applicable policy. Rate limited: calls OPA."""
    system = InventoryService(db).get(system_id)
    service = PolicyService(db)
    checks = service.evaluate_system(
        system,
        jurisdiction_codes=payload.jurisdictions,
        policy_keys=payload.policy_keys,
        reclassify=payload.reclassify,
        actor=user,
    )
    _invalidate_dashboard()
    return PolicyCheckRunResponse(
        ai_system_id=system.id,
        summary=service.summarize(checks),  # type: ignore[arg-type]
        checks=[PolicyCheckRead.model_validate(c) for c in checks],
        checked_at=datetime.now(UTC),
    )


@router.get(
    "/{system_id}/policy-checks",
    response_model=Page[PolicyCheckRead],
    summary="Policy check history (immutable)",
    responses=ERRORS,
)
def list_policy_checks(
    system_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    latest_only: Annotated[bool, Query()] = False,
) -> Page[PolicyCheckRead]:
    InventoryService(db).get(system_id, include_deleted=True)
    service = PolicyService(db)
    if latest_only:
        checks = service.latest_checks(system_id)
        total = len(checks)
    else:
        checks, total = service.check_history(
            system_id, offset=pagination.offset, limit=pagination.page_size
        )
    return Page[PolicyCheckRead].model_validate(
        build_page([PolicyCheckRead.model_validate(c) for c in checks], total, pagination)
    )


# ---------- evidence ----------


@router.post(
    "/{system_id}/evidence",
    response_model=EvidenceAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate an evidence package (async)",
    responses=ERRORS,
)
@limiter.limit(evidence_limit)
def generate_evidence(
    request: Request,
    response: Response,
    system_id: uuid.UUID,
    payload: EvidenceGenerateRequest,
    db: DbSession,
    user: RiskOfficerUser,
) -> EvidenceAcceptedResponse:
    """Queue an evidence package.

    Rate limited: each run renders a PDF and uploads to object storage.
    """
    package = EvidenceGeneratorService(db).request_package(system_id, payload, actor=user)
    db.commit()
    return _dispatch_evidence(db, request, system_id, package)


@router.post(
    "/{system_id}/evidence/{package_id}/retry",
    response_model=EvidenceAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed or stalled evidence package",
    responses={**ERRORS, 409: {"model": ErrorResponse}},
)
@limiter.limit(evidence_limit)
def retry_evidence(
    request: Request,
    response: Response,
    system_id: uuid.UUID,
    package_id: uuid.UUID,
    db: DbSession,
    user: RiskOfficerUser,
) -> EvidenceAcceptedResponse:
    """Re-queue a package that failed, or that has been in flight too long to finish.

    Regenerates with the options of the original request. A completed package, or one
    that is still genuinely generating, answers 409.
    """
    package = EvidenceGeneratorService(db).retry(system_id, package_id, actor=user)
    db.commit()
    return _dispatch_evidence(db, request, system_id, package)


def _dispatch_evidence(
    db: DbSession, request: Request, system_id: uuid.UUID, package: EvidencePackage
) -> EvidenceAcceptedResponse:
    """Queue generation for an already-committed pending package."""
    try:
        task = generate_evidence_package.delay(str(package.id))
    except Exception as exc:  # kombu raises its own OperationalError family
        # The package row is already committed. Leaving it "pending" would show a
        # package that is never going to be generated, so mark it failed and tell the
        # caller the queue is down rather than returning an opaque 500.
        logger.error("evidence_dispatch_failed", package_id=str(package.id), error=str(exc))
        package.status = EvidenceStatus.FAILED
        package.error_message = f"Could not queue the generation job: {exc}"
        db.add(package)
        db.commit()
        raise TaskQueueError() from exc

    package.task_id = task.id
    db.add(package)
    db.flush()

    return EvidenceAcceptedResponse(
        package_id=package.id,
        task_id=task.id,
        status=package.status,
        poll_url=str(
            request.url_for("get_evidence_package", system_id=system_id, package_id=package.id)
        ),
    )


@router.get(
    "/{system_id}/evidence",
    response_model=Page[EvidencePackageRead],
    summary="List evidence packages for a system",
    responses=ERRORS,
)
def list_evidence(
    system_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[EvidencePackageRead]:
    InventoryService(db).get(system_id, include_deleted=True)
    packages, total = EvidenceGeneratorService(db).list_for_system(
        system_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page[EvidencePackageRead].model_validate(
        build_page([EvidencePackageRead.model_validate(p) for p in packages], total, pagination)
    )


@router.get(
    "/{system_id}/evidence/{package_id}",
    response_model=EvidencePackageRead,
    name="get_evidence_package",
    summary="Fetch one evidence package (poll for completion)",
    responses=ERRORS,
)
def get_evidence_package(
    system_id: uuid.UUID, package_id: uuid.UUID, db: DbSession, _: CurrentUser
) -> EvidencePackageRead:
    package = EvidenceGeneratorService(db).get(package_id)
    if package.ai_system_id != system_id:
        raise NotFoundError(f"Evidence package {package_id} not found for system {system_id}.")
    return EvidencePackageRead.model_validate(package)
