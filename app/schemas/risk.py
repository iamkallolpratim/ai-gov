from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import RiskTier
from app.schemas.common import ORMModel
from app.schemas.jurisdiction import JurisdictionDetectionResult, JurisdictionMatch


class RiskClassificationRead(ORMModel):
    id: uuid.UUID
    ai_system_id: uuid.UUID
    jurisdiction_code: str
    risk_tier: RiskTier
    score: float
    is_applicable: bool
    applicability_reasons: list[str]
    metadata_version: int
    evaluated_at: datetime
    evaluated_by_id: uuid.UUID | None
    details: dict[str, Any]


class ClassificationRequest(BaseModel):
    jurisdictions: list[str] | None = Field(
        default=None,
        description="Restrict to these jurisdiction codes; default = auto-detected set.",
        examples=[["EU", "CA"]],
    )
    force: bool = Field(default=False, description="Re-run even if metadata is unchanged.")


class ClassificationResponse(BaseModel):
    ai_system_id: uuid.UUID
    jurisdictions: JurisdictionDetectionResult = Field(
        description="Full engine output: applicability, reasons, order and priority."
    )
    detected_jurisdictions: list[JurisdictionMatch] = Field(
        description="Applicable regimes only. Kept for convenience; see `jurisdictions`."
    )
    classifications: list[RiskClassificationRead]
    most_restrictive_tier: RiskTier
    most_restrictive_jurisdiction: str | None
    evaluated_at: datetime
