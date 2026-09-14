from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class JurisdictionBase(BaseModel):
    code: str = Field(min_length=2, max_length=16, examples=["EU"])
    name: str = Field(examples=["European Union"])
    regulation_name: str | None = Field(default=None, examples=["EU AI Act (Reg. 2024/1689)"])
    description: str | None = None
    is_active: bool = True
    territories: list[str] = Field(default_factory=list, examples=[["EU", "DE", "FR"]])
    risk_taxonomy: dict[str, Any] = Field(default_factory=dict)
    overlay_config: dict[str, Any] = Field(default_factory=dict)


class JurisdictionCreate(JurisdictionBase):
    pass


class JurisdictionUpdate(BaseModel):
    name: str | None = None
    regulation_name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    territories: list[str] | None = None
    risk_taxonomy: dict[str, Any] | None = None
    overlay_config: dict[str, Any] | None = None


class JurisdictionRead(ORMModel, JurisdictionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class JurisdictionMatch(BaseModel):
    """Verdict of the JurisdictionEngine for one regime."""

    code: str = Field(examples=["EU"])
    name: str = Field(examples=["European Union"])
    regulation_name: str | None = Field(default=None, examples=["EU AI Act (Reg. 2024/1689)"])
    applicable: bool = True
    confidence: float = Field(ge=0.0, le=1.0, examples=[0.95])
    reasons: list[str] = Field(examples=[["Offered to users in EU", "Data subjects located in DE"]])
    signals: list[str] = Field(
        default_factory=list,
        description="Machine-readable trigger names behind each reason.",
        examples=[["offering_nexus", "data_subject_nexus"]],
    )
    matched_territories: list[str] = Field(default_factory=list, examples=[["EU"]])
    strictness: int = Field(default=0, examples=[100])


class JurisdictionDetectionResult(BaseModel):
    """Applicable regimes, why they were triggered, and how to sequence the assessment."""

    ai_system_id: uuid.UUID
    matches: list[JurisdictionMatch] = Field(
        description="Every regime evaluated, strictest first; check `applicable`."
    )
    applicable_jurisdictions: list[str] = Field(
        default_factory=list, description="Codes that apply.", examples=[["EU", "CA", "GLOBAL"]]
    )
    evaluation_order: list[str] = Field(
        default_factory=list,
        description="Recommended risk evaluation order: strictest regime first.",
        examples=[["EU", "CA", "GLOBAL"]],
    )
    most_restrictive_jurisdictions: list[str] = Field(
        default_factory=list,
        description="Regimes that win when obligations conflict. A tie returns all of them.",
        examples=[["EU"]],
    )
    apply_most_restrictive: bool = Field(
        default=False,
        description="True when several regimes apply, so the strictest obligation governs.",
    )
    conflict_notes: list[str] = Field(default_factory=list)
    most_restrictive: str | None = Field(
        default=None,
        deprecated=True,
        description="Single strictest regime. Use `most_restrictive_jurisdictions`.",
        examples=["EU"],
    )
    evaluated_at: datetime
