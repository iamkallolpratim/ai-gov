from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Jurisdiction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A regulatory regime (EU AI Act, California, PRC, India, ...)."""

    __tablename__ = "jurisdictions"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    regulation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Country/region codes that pull this jurisdiction into scope.
    territories: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    # Overlay config: tier taxonomy, extraterritorial rules, strictness weight.
    risk_taxonomy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    overlay_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Jurisdiction {self.code}>"
