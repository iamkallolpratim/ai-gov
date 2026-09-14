"""InventoryService: CRUD, search/filter, and metadata version history."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.models.ai_system import AISystem, SystemMetadata, SystemMetadataVersion
from app.models.enums import AuditAction, UserRole
from app.models.risk import RiskClassification
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.system import AISystemCreate, AISystemUpdate, SystemFilters
from app.services.audit import record_audit, split_diff

logger = get_logger(__name__)

SORTABLE_FIELDS = {
    "name": AISystem.name,
    "status": AISystem.status,
    "created_at": AISystem.created_at,
    "updated_at": AISystem.updated_at,
}

_METADATA_FIELDS = (
    "purpose",
    "use_case",
    "industry",
    "autonomy_level",
    "data_categories",
    "deployment_regions",
    "data_subject_regions",
    "data_residency",
    "offered_in_regions",
    "service_accessible_regions",
    "content_accessible_regions",
    "third_party_models",
    "affects_minors",
    "uses_biometrics",
    "uses_generative_ai",
    "is_safety_component",
    "makes_automated_decisions",
    "human_oversight_documented",
    "conformity_assessment_done",
    "technical_documentation_url",
    "training_data_documented",
    "incident_response_plan",
    "attributes",
)


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- reads ----------

    def get(self, system_id: uuid.UUID, *, include_deleted: bool = False) -> AISystem:
        stmt = select(AISystem).where(AISystem.id == system_id)
        if not include_deleted:
            stmt = stmt.where(AISystem.is_deleted.is_(False))
        system = self.db.execute(stmt).unique().scalar_one_or_none()
        if system is None:
            raise NotFoundError(f"AI system {system_id} not found.")
        return system

    def _base_query(self, filters: SystemFilters) -> Select[tuple[AISystem]]:
        stmt = select(AISystem)
        if not filters.include_deleted:
            stmt = stmt.where(AISystem.is_deleted.is_(False))
        if filters.status:
            stmt = stmt.where(AISystem.status.in_([s.value for s in filters.status]))
        if filters.owner_id:
            stmt = stmt.where(AISystem.owner_id == filters.owner_id)

        needs_metadata = any(
            [
                filters.q,
                filters.industry,
                filters.use_case,
                filters.deployment_region,
                filters.uses_generative_ai is not None,
            ]
        )
        if needs_metadata:
            stmt = stmt.outerjoin(SystemMetadata, SystemMetadata.ai_system_id == AISystem.id)
        if filters.q:
            pattern = f"%{filters.q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(AISystem.name).like(pattern),
                    func.lower(func.coalesce(AISystem.description, "")).like(pattern),
                    func.lower(func.coalesce(SystemMetadata.purpose, "")).like(pattern),
                )
            )
        if filters.industry:
            stmt = stmt.where(SystemMetadata.industry == filters.industry)
        if filters.use_case:
            stmt = stmt.where(SystemMetadata.use_case == filters.use_case)
        if filters.deployment_region:
            stmt = stmt.where(
                SystemMetadata.deployment_regions.contains([filters.deployment_region])
            )
        if filters.uses_generative_ai is not None:
            stmt = stmt.where(SystemMetadata.uses_generative_ai.is_(filters.uses_generative_ai))

        if filters.jurisdiction or filters.risk_tier:
            latest = self._latest_classification_subquery()
            stmt = stmt.join(latest, latest.c.ai_system_id == AISystem.id)
            if filters.jurisdiction:
                stmt = stmt.where(latest.c.jurisdiction_code.in_(filters.jurisdiction))
            if filters.risk_tier:
                stmt = stmt.where(latest.c.risk_tier.in_([t.value for t in filters.risk_tier]))
        return stmt

    def _latest_classification_subquery(self):  # type: ignore[no-untyped-def]
        """One row per (system, jurisdiction): the most recent classification."""
        ranked = select(
            RiskClassification.ai_system_id,
            RiskClassification.jurisdiction_code,
            RiskClassification.risk_tier,
            func.row_number()
            .over(
                partition_by=[
                    RiskClassification.ai_system_id,
                    RiskClassification.jurisdiction_code,
                ],
                order_by=RiskClassification.evaluated_at.desc(),
            )
            .label("rn"),
        ).subquery()
        return select(ranked).where(ranked.c.rn == 1).subquery()

    def list_systems(
        self, filters: SystemFilters, pagination: PaginationParams
    ) -> tuple[list[AISystem], int]:
        stmt = self._base_query(filters).distinct()
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        sort_col = SORTABLE_FIELDS.get(pagination.sort_by or "updated_at", AISystem.updated_at)
        stmt = stmt.order_by(sort_col.desc() if pagination.sort_dir == "desc" else sort_col.asc())
        stmt = stmt.offset(pagination.offset).limit(pagination.page_size)
        items = list(self.db.execute(stmt).unique().scalars().all())
        return items, total

    def list_versions(self, system_id: uuid.UUID) -> list[SystemMetadataVersion]:
        self.get(system_id, include_deleted=True)
        stmt = (
            select(SystemMetadataVersion)
            .where(SystemMetadataVersion.ai_system_id == system_id)
            .order_by(SystemMetadataVersion.version.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    # ---------- writes ----------

    def create(self, payload: AISystemCreate, actor: User) -> AISystem:
        owner_id = payload.owner_id or actor.id
        if payload.owner_id and payload.owner_id != actor.id and actor.role != UserRole.ADMIN:
            raise PermissionDeniedError("Only admins may assign a different owner.")
        if self.db.get(User, owner_id) is None:
            raise NotFoundError(f"Owner {owner_id} not found.")

        system = AISystem(
            name=payload.name,
            description=payload.description,
            owner_id=owner_id,
            status=payload.status,
            extra_metadata=payload.metadata,
            metadata_version=1,
        )
        system.system_metadata = SystemMetadata(**payload.system_metadata.model_dump())
        self.db.add(system)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(f"An AI system named '{payload.name}' already exists.") from exc

        self._snapshot(system, actor, "Initial creation", diff={})
        record_audit(
            self.db,
            resource_type="ai_system",
            resource_id=system.id,
            action=AuditAction.CREATE,
            actor=actor,
            new_values={"name": system.name, "status": str(system.status)},
        )
        logger.info("ai_system_created", ai_system_id=str(system.id), name=system.name)
        return system

    def update(self, system_id: uuid.UUID, payload: AISystemUpdate, actor: User) -> AISystem:
        system = self.get(system_id)
        before = self._serialize(system)

        data = payload.model_dump(exclude_unset=True, exclude={"system_metadata", "change_summary"})
        if "owner_id" in data and data["owner_id"] and actor.role != UserRole.ADMIN:
            raise PermissionDeniedError("Only admins may reassign system ownership.")
        if "metadata" in data:
            system.extra_metadata = data.pop("metadata") or {}
        for field, value in data.items():
            setattr(system, field, value)

        if payload.system_metadata is not None:
            if system.system_metadata is None:
                system.system_metadata = SystemMetadata(ai_system_id=system.id)
            meta_data = payload.system_metadata.model_dump(exclude_unset=True)
            for field, value in meta_data.items():
                setattr(system.system_metadata, field, value)

        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(f"An AI system named '{payload.name}' already exists.") from exc

        after = self._serialize(system)
        diff = self._diff(before, after)
        if diff:
            system.metadata_version += 1
            self.db.flush()
            self._snapshot(system, actor, payload.change_summary or "Metadata updated", diff=diff)
        before_values, after_values = split_diff(diff)
        record_audit(
            self.db,
            resource_type="ai_system",
            resource_id=system.id,
            action=AuditAction.UPDATE,
            actor=actor,
            old_values=before_values,
            new_values=after_values,
        )
        logger.info("ai_system_updated", ai_system_id=str(system.id), changed=list(diff))
        return system

    def soft_delete(self, system_id: uuid.UUID, actor: User) -> None:
        system = self.get(system_id)
        system.soft_delete()
        system.metadata_version += 1
        self.db.flush()
        self._snapshot(system, actor, "System soft-deleted", diff={"is_deleted": [False, True]})
        record_audit(
            self.db,
            resource_type="ai_system",
            resource_id=system.id,
            action=AuditAction.DELETE,
            actor=actor,
        )
        logger.info("ai_system_soft_deleted", ai_system_id=str(system.id))

    def restore(self, system_id: uuid.UUID, actor: User) -> AISystem:
        system = self.get(system_id, include_deleted=True)
        if not system.is_deleted:
            return system
        system.is_deleted = False
        system.deleted_at = None
        system.metadata_version += 1
        self.db.flush()
        self._snapshot(system, actor, "System restored", diff={"is_deleted": [True, False]})
        record_audit(
            self.db,
            resource_type="ai_system",
            resource_id=system.id,
            action=AuditAction.UPDATE,
            actor=actor,
            new_values={"restored": True},
        )
        return system

    # ---------- helpers ----------

    @staticmethod
    def _serialize(system: AISystem) -> dict[str, Any]:
        meta = system.system_metadata
        snapshot: dict[str, Any] = {
            "name": system.name,
            "description": system.description,
            "owner_id": str(system.owner_id),
            "status": str(system.status),
            "metadata": system.extra_metadata,
            "is_deleted": system.is_deleted,
        }
        if meta is not None:
            snapshot["system_metadata"] = {
                field: _jsonable(getattr(meta, field)) for field in _METADATA_FIELDS
            }
        return snapshot

    @staticmethod
    def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for key in set(before) | set(after):
            old, new = before.get(key), after.get(key)
            if key == "system_metadata" and isinstance(old, dict) and isinstance(new, dict):
                nested = {
                    k: [old.get(k), new.get(k)]
                    for k in set(old) | set(new)
                    if old.get(k) != new.get(k)
                }
                if nested:
                    diff[key] = nested
            elif old != new:
                diff[key] = [old, new]
        return diff

    def _snapshot(
        self, system: AISystem, actor: User | None, summary: str, *, diff: dict[str, Any]
    ) -> SystemMetadataVersion:
        version = SystemMetadataVersion(
            ai_system_id=system.id,
            version=system.metadata_version,
            changed_by_id=actor.id if actor else None,
            change_summary=summary,
            snapshot=self._serialize(system),
            diff=diff,
        )
        self.db.add(version)
        self.db.flush()
        return version


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):  # StrEnum
        return str(value)
    return value
