"""Domain enumerations shared by models and schemas."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    RISK_OFFICER = "risk_officer"
    VIEWER = "viewer"


class SystemStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class AutonomyLevel(StrEnum):
    HUMAN_IN_THE_LOOP = "human_in_the_loop"
    HUMAN_ON_THE_LOOP = "human_on_the_loop"
    FULLY_AUTONOMOUS = "fully_autonomous"


class RiskTier(StrEnum):
    """Global baseline tiers; regional overlays map onto these."""

    PROHIBITED = "prohibited"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"
    UNKNOWN = "unknown"


RISK_TIER_ORDER: dict[str, int] = {
    RiskTier.UNKNOWN: 0,
    RiskTier.MINIMAL: 1,
    RiskTier.LIMITED: 2,
    RiskTier.HIGH: 3,
    RiskTier.PROHIBITED: 4,
}


class PolicySeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PolicyResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    ERROR = "error"


class EvidenceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ActorType(StrEnum):
    USER = "user"
    #: The synthetic principal used when authentication is disabled.
    SYSTEM = "system"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CLASSIFY = "classify"
    POLICY_CHECK = "policy_check"
    EVIDENCE_GENERATE = "evidence_generate"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    READ = "read"
