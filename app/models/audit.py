from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import ActorType, AuditAction


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """Append-only audit trail for every mutating or compliance-relevant action.

    Written in both authentication modes. With AUTH_DISABLED set, entries are attributed
    to the synthetic system principal rather than being skipped — an unauthenticated
    deployment still has to be able to answer "who changed this, and when".

    UPDATE and DELETE are rejected by database triggers, so rows here are permanent.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id", "created_at"),
        Index("ix_audit_logs_actor_time", "actor_id", "created_at"),
    )

    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action", native_enum=False, length=32), nullable=False
    )

    # --- actor ---
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    actor_type: Mapped[ActorType] = mapped_column(
        SAEnum(ActorType, name="actor_type", native_enum=False, length=16),
        default=ActorType.USER,
        nullable=False,
        index=True,
    )
    #: Stable text label: the user's UUID, or "system" when auth is disabled. Survives
    #: the actor row being deleted, which nulls actor_id.
    actor_label: Mapped[str] = mapped_column(String(64), default="system", nullable=False)

    # --- request fingerprint ---
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- what changed ---
    old_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    new_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    @property
    def correlation_id(self) -> str | None:
        """Previous name for `request_id`."""
        return self.request_id
