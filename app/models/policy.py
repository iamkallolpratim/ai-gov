from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PolicyResult, PolicySeverity

if TYPE_CHECKING:
    from app.models.ai_system import AISystem


class Policy(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A policy-as-code rule, versioned per jurisdiction."""

    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_policies_key_version"),
        Index("ix_policies_jurisdiction_active", "jurisdiction_code", "is_active"),
    )

    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    jurisdiction_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("jurisdictions.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    severity: Mapped[PolicySeverity] = mapped_column(
        SAEnum(PolicySeverity, name="policy_severity", native_enum=False, length=32),
        default=PolicySeverity.MEDIUM,
        nullable=False,
        index=True,
    )
    # OPA package path, e.g. "aigov.eu.high_risk".
    opa_package: Mapped[str] = mapped_column(String(255), nullable=False)
    # Rego source of record; pushed to OPA on sync.
    rego_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Fallback declarative rules used when OPA is unreachable.
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Only evaluate when the system is in one of these tiers (empty = always).
    applies_to_risk_tiers: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Policy {self.key}@{self.version} {self.jurisdiction_code}>"


class PolicyCheck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable record of one policy evaluation against one system."""

    __tablename__ = "policy_checks"
    __table_args__ = (
        Index("ix_policy_checks_system_time", "ai_system_id", "checked_at"),
        Index("ix_policy_checks_result_jur", "result", "jurisdiction_code"),
    )

    ai_system_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    policy_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    jurisdiction_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    severity: Mapped[PolicySeverity] = mapped_column(
        SAEnum(PolicySeverity, name="policy_severity", native_enum=False, length=32),
        nullable=False,
    )
    result: Mapped[PolicyResult] = mapped_column(
        SAEnum(PolicyResult, name="policy_result", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    violations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    remediation: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    evaluated_input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    raw_opa_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    engine: Mapped[str] = mapped_column(String(32), default="opa", nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    checked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    ai_system: Mapped[AISystem] = relationship("AISystem", back_populates="policy_checks")
    policy: Mapped[Policy] = relationship("Policy", lazy="joined")
