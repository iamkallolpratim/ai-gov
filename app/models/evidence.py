from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EvidenceStatus

if TYPE_CHECKING:
    from app.models.ai_system import AISystem


class EvidencePackage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A generated compliance evidence bundle (PDF + JSON) in object storage."""

    __tablename__ = "evidence_packages"

    ai_system_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jurisdictions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        SAEnum(EvidenceStatus, name="evidence_status", native_enum=False, length=32),
        default=EvidenceStatus.PENDING,
        nullable=False,
        index=True,
    )
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    pdf_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    json_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    json_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    ai_system: Mapped[AISystem] = relationship("AISystem", back_populates="evidence_packages")
