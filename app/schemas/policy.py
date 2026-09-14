from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PolicyResult, PolicySeverity, RiskTier
from app.schemas.common import ORMModel


class PolicyBase(BaseModel):
    key: str = Field(min_length=1, max_length=128, examples=["eu_high_risk_human_oversight"])
    name: str = Field(examples=["EU AI Act Art. 14 - Human oversight"])
    description: str | None = None
    jurisdiction_code: str = Field(examples=["EU"])
    version: str = Field(default="1.0.0", examples=["1.0.0"])
    severity: PolicySeverity = PolicySeverity.MEDIUM
    opa_package: str = Field(examples=["aigov.eu.high_risk"])
    rego_code: str | None = None
    rules: dict[str, Any] = Field(default_factory=dict)
    remediation: str | None = None
    applies_to_risk_tiers: list[RiskTier] = Field(default_factory=list, examples=[["high"]])
    is_active: bool = True


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    severity: PolicySeverity | None = None
    opa_package: str | None = None
    rego_code: str | None = None
    rules: dict[str, Any] | None = None
    remediation: str | None = None
    applies_to_risk_tiers: list[RiskTier] | None = None
    is_active: bool | None = None
    version: str | None = None


class PolicyRead(ORMModel, PolicyBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PolicyViolation(BaseModel):
    """One rule that fired, in the shape the console renders."""

    model_config = ConfigDict(extra="allow")

    rule_id: str = Field(examples=["eu.high_risk.art_14.human_oversight_missing"])
    article: str | None = Field(default=None, examples=["Art. 14"])
    severity: PolicySeverity = Field(examples=["critical"])
    msg: str = Field(examples=["No human oversight measures are documented. Art. 14 requires ..."])
    remediation: str | None = Field(
        default=None,
        examples=["Assign named oversight roles, document how reviewers intervene ..."],
    )


class PolicyCheckRead(ORMModel):
    id: uuid.UUID
    ai_system_id: uuid.UUID
    policy_id: uuid.UUID
    policy_key: str
    policy_version: str
    jurisdiction_code: str
    severity: PolicySeverity
    result: PolicyResult
    explanation: str
    violations: list[PolicyViolation]
    remediation: list[str]
    raw_opa_response: dict[str, Any]
    engine: str
    checked_at: datetime
    checked_by_id: uuid.UUID | None


class PolicyCheckRequest(BaseModel):
    jurisdictions: list[str] | None = Field(
        default=None, description="Default = jurisdictions applicable to the system."
    )
    policy_keys: list[str] | None = Field(
        default=None, description="Restrict to specific policies."
    )
    reclassify: bool = Field(
        default=True, description="Run jurisdiction + risk classification first."
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"jurisdictions": ["EU"], "reclassify": True}}
    )


class PolicyCheckRunSummary(BaseModel):
    total: int
    passed: int
    failed: int
    warnings: int
    errors: int
    compliant: bool


class PolicyCheckRunResponse(BaseModel):
    ai_system_id: uuid.UUID
    summary: PolicyCheckRunSummary
    checks: list[PolicyCheckRead]
    checked_at: datetime


class BatchPolicyCheckRequest(BaseModel):
    ai_system_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    jurisdictions: list[str] | None = None
    policy_keys: list[str] | None = None
    reclassify: bool = True


class BatchPolicyCheckResponse(BaseModel):
    results: list[PolicyCheckRunResponse]
