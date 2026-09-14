"""EvidenceGeneratorService: assemble, render, and store compliance evidence.

The HTTP layer creates a PENDING package row and dispatches a Celery task; the worker
calls :meth:`EvidenceGeneratorService.build` to do the work.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.ai_system import SystemMetadataVersion
from app.models.enums import AuditAction, EvidenceStatus
from app.models.evidence import EvidencePackage
from app.models.user import User
from app.schemas.evidence import EvidenceGenerateRequest
from app.services.audit import record_audit
from app.services.inventory import InventoryService
from app.services.pdf import render_evidence_pdf
from app.services.policy import PolicyService
from app.services.risk import RiskClassificationService
from app.services.storage import ObjectStorage, get_storage

logger = get_logger(__name__)

IN_FLIGHT_STATUSES = (EvidenceStatus.PENDING, EvidenceStatus.RUNNING)


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; PostgreSQL hands back aware ones."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class EvidenceGeneratorService:
    def __init__(self, db: Session, storage: ObjectStorage | None = None) -> None:
        self.db = db
        self._storage = storage
        self.inventory = InventoryService(db)
        self.risk = RiskClassificationService(db)
        self.policy = PolicyService(db)

    @property
    def storage(self) -> ObjectStorage:
        if self._storage is None:
            self._storage = get_storage()
        return self._storage

    # ---------- lifecycle ----------

    def request_package(
        self, system_id: uuid.UUID, payload: EvidenceGenerateRequest, actor: User
    ) -> EvidencePackage:
        system = self.inventory.get(system_id)
        jurisdictions = payload.jurisdictions or [
            code for code, c in self.risk.latest_for_system(system.id).items() if c.is_applicable
        ]
        package = EvidencePackage(
            ai_system_id=system.id,
            jurisdictions=[j.upper() for j in jurisdictions],
            status=EvidenceStatus.PENDING,
            generated_by_id=actor.id,
            summary={"options": payload.model_dump()},
        )
        self.db.add(package)
        self.db.flush()
        record_audit(
            self.db,
            resource_type="evidence_package",
            resource_id=package.id,
            action=AuditAction.EVIDENCE_GENERATE,
            actor=actor,
            new_values={"ai_system_id": str(system.id), "jurisdictions": package.jurisdictions},
        )
        return package

    def get(self, package_id: uuid.UUID) -> EvidencePackage:
        package = self.db.get(EvidencePackage, package_id)
        if package is None:
            raise NotFoundError(f"Evidence package {package_id} not found.")
        return package

    def list_for_system(
        self, system_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[EvidencePackage], int]:
        stmt = select(EvidencePackage).where(EvidencePackage.ai_system_id == system_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(EvidencePackage.created_at.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all()), total

    # ---------- recovery ----------

    @staticmethod
    def stale_cutoff(now: datetime | None = None) -> datetime:
        return (now or datetime.now(UTC)) - timedelta(seconds=settings.EVIDENCE_STALE_AFTER_SECONDS)

    def is_stale(self, package: EvidencePackage, now: datetime | None = None) -> bool:
        """In flight, with no activity for longer than any real generation job takes.

        Measured from `updated_at` — the last queue, retry or worker start — never from
        `created_at`. A package first requested weeks ago and retried a second ago is
        freshly in flight; judging it by its creation date made every retry look stalled
        the moment it was queued.
        """
        return package.status in IN_FLIGHT_STATUSES and _as_utc(
            package.updated_at
        ) < self.stale_cutoff(now)

    def expire_stale(self, now: datetime | None = None) -> int:
        """Mark packages that will never finish as failed, so they become retryable.

        Filters on status in SQL and on age in Python: in-flight rows are few by nature,
        and comparing timezone-aware values in Python is identical on SQLite and
        PostgreSQL, where a SQL comparison is not.
        """
        cutoff = self.stale_cutoff(now)
        in_flight = (
            self.db.execute(
                select(EvidencePackage).where(EvidencePackage.status.in_(IN_FLIGHT_STATUSES))
            )
            .scalars()
            .all()
        )
        stale = [p for p in in_flight if _as_utc(p.updated_at) < cutoff]

        minutes = settings.EVIDENCE_STALE_AFTER_SECONDS // 60
        for package in stale:
            previous = str(package.status)
            package.status = EvidenceStatus.FAILED
            package.error_message = (
                f"Generation did not complete within {minutes} minutes and was marked "
                "failed. Retry to generate it again."
            )
            record_audit(
                self.db,
                resource_type="evidence_package",
                resource_id=package.id,
                action=AuditAction.UPDATE,
                actor=None,
                old_values={"status": previous},
                new_values={"status": str(EvidenceStatus.FAILED), "reason": "stale"},
            )
        if stale:
            self.db.flush()
            logger.warning("evidence_packages_expired", count=len(stale))
        return len(stale)

    def retry(self, system_id: uuid.UUID, package_id: uuid.UUID, actor: User) -> EvidencePackage:
        """Reset a failed or stalled package to pending so it can be queued again.

        The original request options stay in `summary["options"]`, which `build()` reads,
        so a retry regenerates exactly what was asked for.
        """
        package = self.get(package_id)
        if package.ai_system_id != system_id:
            raise NotFoundError(f"Evidence package {package_id} not found for system {system_id}.")
        if package.status == EvidenceStatus.COMPLETED:
            raise ConflictError(
                "This package already completed. Generate a new package to refresh it."
            )
        if package.status in IN_FLIGHT_STATUSES and not self.is_stale(package):
            raise ConflictError("This package is still being generated.")

        previous = str(package.status)
        package.status = EvidenceStatus.PENDING
        package.error_message = None
        package.task_id = None
        package.updated_at = datetime.now(UTC)  # restarts the staleness clock
        self.db.flush()
        record_audit(
            self.db,
            resource_type="evidence_package",
            resource_id=package.id,
            action=AuditAction.EVIDENCE_GENERATE,
            actor=actor,
            old_values={"status": previous},
            new_values={"status": str(EvidenceStatus.PENDING), "retry": True},
        )
        return package

    def build(self, package_id: uuid.UUID) -> EvidencePackage:
        """Run the full generation pipeline for a pending package."""
        package = self.get(package_id)
        package.status = EvidenceStatus.RUNNING
        self.db.flush()

        try:
            options = EvidenceGenerateRequest(**(package.summary.get("options") or {}))
            system = self.inventory.get(package.ai_system_id, include_deleted=True)

            if options.refresh_checks:
                actor = (
                    self.db.get(User, package.generated_by_id) if package.generated_by_id else None
                )
                self.policy.evaluate_system(
                    system, jurisdiction_codes=package.jurisdictions or None, actor=actor
                )

            document = self.assemble(package, options)
            pdf_bytes = render_evidence_pdf(document)
            json_bytes = json.dumps(document, indent=2, default=str).encode()

            prefix = f"evidence/{system.id}/{package.id}"
            pdf_key = f"{prefix}/evidence.pdf"
            json_key = f"{prefix}/evidence.json"
            self.storage.put_bytes(pdf_key, pdf_bytes, "application/pdf")
            self.storage.put_bytes(json_key, json_bytes, "application/json")

            package.pdf_object_key = pdf_key
            package.json_object_key = json_key
            package.file_url = self.storage.presigned_url(pdf_key)
            package.json_url = self.storage.presigned_url(json_key)
            package.checksum_sha256 = hashlib.sha256(pdf_bytes + json_bytes).hexdigest()
            package.summary = {**package.summary, **document.get("summary", {})}
            package.status = EvidenceStatus.COMPLETED
            package.generated_at = datetime.now(UTC)
            package.error_message = None
            self.db.flush()
            logger.info(
                "evidence_package_completed",
                package_id=str(package.id),
                ai_system_id=str(system.id),
            )
        except Exception as exc:  # noqa: BLE001 - persist the failure for the API to surface
            package.status = EvidenceStatus.FAILED
            package.error_message = f"{type(exc).__name__}: {exc}"
            self.db.flush()
            logger.error("evidence_package_failed", package_id=str(package.id), error=str(exc))
            raise
        return package

    # ---------- assembly ----------

    def assemble(
        self, package: EvidencePackage, options: EvidenceGenerateRequest
    ) -> dict[str, Any]:
        system = self.inventory.get(package.ai_system_id, include_deleted=True)
        meta = system.system_metadata
        codes = {c.upper() for c in (package.jurisdictions or [])}

        classifications = [
            c
            for c in self.risk.latest_for_system(system.id).values()
            if not codes or c.jurisdiction_code in codes
        ]
        checks = []
        if options.include_policy_checks:
            checks = [
                c
                for c in self.policy.latest_checks(system.id)
                if not codes or c.jurisdiction_code in codes
            ]

        history: list[dict[str, Any]] = []
        if options.include_history:
            versions = (
                self.db.execute(
                    select(SystemMetadataVersion)
                    .where(SystemMetadataVersion.ai_system_id == system.id)
                    .order_by(SystemMetadataVersion.version.desc())
                )
                .scalars()
                .all()
            )
            history = [
                {
                    "version": v.version,
                    "created_at": v.created_at.isoformat(),
                    "change_summary": v.change_summary,
                    "diff": v.diff,
                }
                for v in versions
            ]

        owner = self.db.get(User, system.owner_id)
        generator = self.db.get(User, package.generated_by_id) if package.generated_by_id else None

        return {
            "schema_version": "1.0.0",
            "package_id": str(package.id),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "generated_by": generator.email if generator else None,
            "jurisdictions": sorted(codes) or [c.jurisdiction_code for c in classifications],
            "notes": options.notes,
            "system": {
                "id": str(system.id),
                "name": system.name,
                "description": system.description,
                "status": str(system.status),
                "owner": owner.email if owner else None,
                "metadata_version": system.metadata_version,
                "extra_metadata": system.extra_metadata,
                "created_at": system.created_at.isoformat(),
            },
            "metadata": {
                "purpose": meta.purpose if meta else None,
                "use_case": meta.use_case if meta else None,
                "industry": meta.industry if meta else None,
                "autonomy_level": str(meta.autonomy_level) if meta else None,
                "data_categories": meta.data_categories if meta else [],
                "deployment_regions": meta.deployment_regions if meta else [],
                "data_subject_regions": meta.data_subject_regions if meta else [],
                "data_residency": meta.data_residency if meta else [],
                "third_party_models": meta.third_party_models if meta else [],
                "affects_minors": bool(meta and meta.affects_minors),
                "uses_biometrics": bool(meta and meta.uses_biometrics),
                "uses_generative_ai": bool(meta and meta.uses_generative_ai),
                "is_safety_component": bool(meta and meta.is_safety_component),
                "makes_automated_decisions": bool(meta and meta.makes_automated_decisions),
                "human_oversight_documented": bool(meta and meta.human_oversight_documented),
                "conformity_assessment_done": bool(meta and meta.conformity_assessment_done),
                "technical_documentation_url": meta.technical_documentation_url if meta else None,
                "training_data_documented": bool(meta and meta.training_data_documented),
                "incident_response_plan": bool(meta and meta.incident_response_plan),
                "attributes": meta.attributes if meta else {},
            },
            "classifications": [
                {
                    "jurisdiction_code": c.jurisdiction_code,
                    "risk_tier": str(c.risk_tier),
                    "score": c.score,
                    "is_applicable": c.is_applicable,
                    "applicability_reasons": c.applicability_reasons,
                    "evaluated_at": c.evaluated_at.isoformat(),
                    "details": c.details,
                }
                for c in classifications
            ],
            "policy_checks": [
                {
                    "policy_key": c.policy_key,
                    "policy_version": c.policy_version,
                    "jurisdiction_code": c.jurisdiction_code,
                    "severity": str(c.severity),
                    "result": str(c.result),
                    "explanation": c.explanation,
                    "violations": c.violations,
                    "remediation": c.remediation,
                    "engine": c.engine,
                    "checked_at": c.checked_at.isoformat(),
                }
                for c in checks
            ],
            "history": history,
            "summary": self.policy.summarize(checks),
        }
