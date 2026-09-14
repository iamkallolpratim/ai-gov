from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AutonomyLevel, SystemStatus

if TYPE_CHECKING:
    from app.models.evidence import EvidencePackage
    from app.models.policy import PolicyCheck
    from app.models.risk import RiskClassification
    from app.models.user import User


class AISystem(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """An AI system in the organisation's inventory."""

    __tablename__ = "ai_systems"
    __table_args__ = (
        UniqueConstraint("name", name="uq_ai_systems_name"),
        Index("ix_ai_systems_status_deleted", "status", "is_deleted"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[SystemStatus] = mapped_column(
        SAEnum(SystemStatus, name="system_status", native_enum=False, length=32),
        default=SystemStatus.DRAFT,
        nullable=False,
        index=True,
    )
    # Free-form extras beyond the structured SystemMetadata row.
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    metadata_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    owner: Mapped[User] = relationship("User", lazy="joined")
    system_metadata: Mapped[SystemMetadata | None] = relationship(
        "SystemMetadata",
        back_populates="ai_system",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    metadata_versions: Mapped[list[SystemMetadataVersion]] = relationship(
        "SystemMetadataVersion",
        back_populates="ai_system",
        cascade="all, delete-orphan",
        order_by="desc(SystemMetadataVersion.version)",
    )
    classifications: Mapped[list[RiskClassification]] = relationship(
        "RiskClassification", back_populates="ai_system", cascade="all, delete-orphan"
    )
    policy_checks: Mapped[list[PolicyCheck]] = relationship(
        "PolicyCheck", back_populates="ai_system", cascade="all, delete-orphan"
    )
    evidence_packages: Mapped[list[EvidencePackage]] = relationship(
        "EvidencePackage", back_populates="ai_system", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AISystem {self.name} status={self.status}>"


class SystemMetadata(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured compliance-relevant attributes driving classification."""

    __tablename__ = "system_metadata"

    ai_system_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_case: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    autonomy_level: Mapped[AutonomyLevel] = mapped_column(
        SAEnum(AutonomyLevel, name="autonomy_level", native_enum=False, length=32),
        default=AutonomyLevel.HUMAN_IN_THE_LOOP,
        nullable=False,
    )
    data_categories: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    deployment_regions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    data_subject_regions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    data_residency: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    # Markets the system is actively offered/marketed to, where the service can be
    # reached at all, and where its generated output can be viewed. These are distinct
    # from deployment: a service hosted only in the US can still be offered into the EU
    # and reachable from China.
    offered_in_regions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    service_accessible_regions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    content_accessible_regions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    third_party_models: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    affects_minors: Mapped[bool] = mapped_column(default=False, nullable=False)
    uses_biometrics: Mapped[bool] = mapped_column(default=False, nullable=False)
    uses_generative_ai: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_safety_component: Mapped[bool] = mapped_column(default=False, nullable=False)
    makes_automated_decisions: Mapped[bool] = mapped_column(default=False, nullable=False)
    human_oversight_documented: Mapped[bool] = mapped_column(default=False, nullable=False)
    conformity_assessment_done: Mapped[bool] = mapped_column(default=False, nullable=False)
    technical_documentation_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    training_data_documented: Mapped[bool] = mapped_column(default=False, nullable=False)
    incident_response_plan: Mapped[bool] = mapped_column(default=False, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    ai_system: Mapped[AISystem] = relationship("AISystem", back_populates="system_metadata")


class SystemMetadataVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable snapshot of system + metadata at each mutation."""

    __tablename__ = "system_metadata_versions"
    __table_args__ = (
        UniqueConstraint("ai_system_id", "version", name="uq_system_metadata_versions_version"),
    )

    ai_system_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    ai_system: Mapped[AISystem] = relationship("AISystem", back_populates="metadata_versions")
