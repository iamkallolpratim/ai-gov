from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PolicyResult, PolicySeverity, RiskTier, SystemStatus


class RiskTierCount(BaseModel):
    risk_tier: RiskTier
    count: int


class JurisdictionCompliance(BaseModel):
    jurisdiction_code: str = Field(examples=["EU"])
    jurisdiction_name: str = Field(examples=["European Union"])
    systems_in_scope: int
    compliant_systems: int
    non_compliant_systems: int
    unassessed_systems: int
    compliance_rate: float = Field(ge=0.0, le=1.0, examples=[0.72])
    risk_tiers: list[RiskTierCount]
    open_failures: int
    critical_failures: int


class RecentFailure(BaseModel):
    check_id: uuid.UUID
    ai_system_id: uuid.UUID
    ai_system_name: str
    policy_key: str
    policy_name: str
    jurisdiction_code: str
    severity: PolicySeverity
    result: PolicyResult
    explanation: str
    checked_at: datetime


class PendingReview(BaseModel):
    ai_system_id: uuid.UUID
    ai_system_name: str
    status: SystemStatus
    reason: str = Field(examples=["Never classified"])
    last_evaluated_at: datetime | None


class DashboardSummary(BaseModel):
    total_systems: int
    active_systems: int
    draft_systems: int
    retired_systems: int
    systems_assessed: int
    systems_never_assessed: int
    overall_compliance_score: float = Field(ge=0.0, le=100.0, examples=[78.5])
    risk_tiers: list[RiskTierCount]
    jurisdictions_in_scope: int
    open_failures: int
    critical_failures: int
    evidence_packages_30d: int
    recent_failures: list[RecentFailure]
    pending_reviews: list[PendingReview]
    generated_at: datetime


class JurisdictionDashboard(BaseModel):
    jurisdictions: list[JurisdictionCompliance]
    generated_at: datetime
