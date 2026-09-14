"""Celery tasks: evidence generation, scheduled re-checks, cache warming.

Tasks are bound with `@celery_app.task`, never `@shared_task`. `shared_task` resolves its
app through a thread-local, and on a request thread that had not imported the Celery app it
bound to Celery's broker-less default app — the cause of intermittent
`[Errno 111] Connection refused` when queueing evidence from the API.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.core.context import set_correlation_id
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.ai_system import AISystem
from app.models.enums import EvidenceStatus
from app.models.evidence import EvidencePackage
from app.services.dashboard import DashboardService
from app.services.evidence import EvidenceGeneratorService
from app.services.policy import PolicyService
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_evidence_package",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    acks_late=True,
)
def generate_evidence_package(
    self: Any, package_id: str, correlation_id: str | None = None
) -> dict[str, Any]:
    """Assemble, render, and upload an evidence package."""
    set_correlation_id(correlation_id)
    logger.info("evidence_task_started", package_id=package_id, attempt=self.request.retries + 1)

    with session_scope() as db:
        package = db.get(EvidencePackage, uuid.UUID(package_id))
        if package is None:
            logger.error("evidence_task_missing_package", package_id=package_id)
            return {"package_id": package_id, "status": "missing"}
        if package.status == EvidenceStatus.COMPLETED:
            return {"package_id": package_id, "status": str(package.status)}
        package.task_id = self.request.id

    with session_scope() as db:
        result = EvidenceGeneratorService(db).build(uuid.UUID(package_id))
        return {
            "package_id": package_id,
            "status": str(result.status),
            "file_url": result.file_url,
            "json_url": result.json_url,
            "checksum_sha256": result.checksum_sha256,
        }


@celery_app.task(name="app.workers.tasks.recheck_system_policies")
def recheck_system_policies(system_id: str, correlation_id: str | None = None) -> dict[str, Any]:
    """Re-classify and re-evaluate one system out of band."""
    set_correlation_id(correlation_id)
    with session_scope() as db:
        system = db.get(AISystem, uuid.UUID(system_id))
        if system is None or system.is_deleted:
            return {"system_id": system_id, "status": "missing"}
        service = PolicyService(db)
        checks = service.evaluate_system(system, reclassify=True)
        return {"system_id": system_id, **service.summarize(checks)}


@celery_app.task(name="app.workers.tasks.recheck_all_systems")
def recheck_all_systems() -> dict[str, int]:
    """Portfolio-wide re-evaluation, typically run on a schedule."""
    with session_scope() as db:
        ids = [
            str(row)
            for row in db.execute(select(AISystem.id).where(AISystem.is_deleted.is_(False)))
            .scalars()
            .all()
        ]
    for system_id in ids:
        recheck_system_policies.delay(system_id)
    return {"dispatched": len(ids)}


@celery_app.task(name="app.workers.tasks.refresh_dashboard_cache")
def refresh_dashboard_cache() -> dict[str, bool]:
    with session_scope() as db:
        service = DashboardService(db)
        service.summary(use_cache=False)
        service.by_jurisdiction(use_cache=False)
    return {"refreshed": True}


@celery_app.task(name="app.workers.tasks.expire_stale_evidence_packages")
def expire_stale_evidence_packages() -> dict[str, int]:
    """Fail packages that have been pending or running long enough that they never will.

    A package can be stranded if its dispatch failed before the API handled that case, or
    if a worker died mid-job. Left alone it shows "Generating…" forever and keeps every
    open evidence view polling.
    """
    with session_scope() as db:
        expired = EvidenceGeneratorService(db).expire_stale()
    return {"expired": expired}
