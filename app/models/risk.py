from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RiskTier

if TYPE_CHECKING:
    from app.models.ai_system import AISystem


class RiskClassification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable, append-only risk classification for one system/jurisdiction."""

    __tablename__ = "risk_classifications"
    __table_args__ = (
        Index("ix_risk_class_system_jur_time", "ai_system_id", "jurisdiction_code", "evaluated_at"),
    )

    ai_system_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jurisdiction_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("jurisdictions.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    risk_tier: Mapped[RiskTier] = mapped_column(
        SAEnum(RiskTier, name="risk_tier", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_applicable: Mapped[bool] = mapped_column(default=True, nullable=False)
    applicability_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    metadata_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    evaluated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    ai_system: Mapped[AISystem] = relationship("AISystem", back_populates="classifications")
