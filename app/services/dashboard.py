"""DashboardService: cached compliance aggregates by jurisdiction and risk tier."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.ai_system import AISystem
from app.models.enums import PolicyResult, PolicySeverity, RiskTier, SystemStatus
from app.models.evidence import EvidencePackage
from app.models.jurisdiction import Jurisdiction
from app.models.policy import Policy, PolicyCheck
from app.models.risk import RiskClassification
from app.services.cache import cache_get, cache_set

logger = get_logger(__name__)

SUMMARY_CACHE_KEY = "dashboard:summary:v1"
JURISDICTION_CACHE_KEY = "dashboard:by_jurisdiction:v1"


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- shared building blocks ----------

    def _latest_classifications(self) -> list[RiskClassification]:
        """Latest classification per (system, jurisdiction) for live systems."""
        ranked = (
            select(
                RiskClassification,
                func.row_number()
                .over(
                    partition_by=[
                        RiskClassification.ai_system_id,
                        RiskClassification.jurisdiction_code,
                    ],
                    order_by=RiskClassification.evaluated_at.desc(),
                )
                .label("rn"),
            )
            .join(AISystem, AISystem.id == RiskClassification.ai_system_id)
            .where(AISystem.is_deleted.is_(False))
            .subquery()
        )
        stmt = select(RiskClassification).join(
            ranked,
            (ranked.c.id == RiskClassification.id) & (ranked.c.rn == 1),
        )
        return list(self.db.execute(stmt).scalars().all())

    def _latest_checks(self) -> list[PolicyCheck]:
        ranked = (
            select(
                PolicyCheck,
                func.row_number()
                .over(
                    partition_by=[
                        PolicyCheck.ai_system_id,
                        PolicyCheck.jurisdiction_code,
                        PolicyCheck.policy_key,
                    ],
                    order_by=PolicyCheck.checked_at.desc(),
                )
                .label("rn"),
            )
            .join(AISystem, AISystem.id == PolicyCheck.ai_system_id)
            .where(AISystem.is_deleted.is_(False))
            .subquery()
        )
        stmt = select(PolicyCheck).join(
            ranked, (ranked.c.id == PolicyCheck.id) & (ranked.c.rn == 1)
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    # ---------- public API ----------

    def summary(self, *, use_cache: bool = True) -> dict[str, Any]:
        if use_cache and (cached := cache_get(SUMMARY_CACHE_KEY)):
            return cached

        status_counts: dict[str, int] = {
            str(status): count
            for status, count in self.db.execute(
                select(AISystem.status, func.count())
                .where(AISystem.is_deleted.is_(False))
                .group_by(AISystem.status)
            ).all()
        }
        total = sum(status_counts.values())

        classifications = self._latest_classifications()
        assessed_ids = {c.ai_system_id for c in classifications}
        tier_counter: Counter[str] = Counter()
        for c in classifications:
            if c.is_applicable:
                tier_counter[str(c.risk_tier)] += 1

        checks = self._latest_checks()
        failures = [c for c in checks if c.result == PolicyResult.FAIL]
        critical = [c for c in failures if c.severity == PolicySeverity.CRITICAL]

        systems_with_failures = {c.ai_system_id for c in failures}
        compliant = len(assessed_ids - systems_with_failures)
        score = round((compliant / total) * 100, 1) if total else 0.0

        since = datetime.now(UTC) - timedelta(days=30)
        evidence_30d = self.db.execute(
            select(func.count())
            .select_from(EvidencePackage)
            .where(EvidencePackage.created_at >= since)
        ).scalar_one()

        return self._cache(
            SUMMARY_CACHE_KEY,
            {
                "total_systems": total,
                "active_systems": status_counts.get(SystemStatus.ACTIVE, 0),
                "draft_systems": status_counts.get(SystemStatus.DRAFT, 0),
                "retired_systems": status_counts.get(SystemStatus.RETIRED, 0),
                "systems_assessed": len(assessed_ids),
                "systems_never_assessed": max(total - len(assessed_ids), 0),
                "overall_compliance_score": score,
                "risk_tiers": self._tier_rows(tier_counter),
                "jurisdictions_in_scope": len(
                    {c.jurisdiction_code for c in classifications if c.is_applicable}
                ),
                "open_failures": len(failures),
                "critical_failures": len(critical),
                "evidence_packages_30d": evidence_30d,
                "recent_failures": self.recent_failures(limit=10),
                "pending_reviews": self.pending_reviews(limit=10),
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

    def by_jurisdiction(self, *, use_cache: bool = True) -> dict[str, Any]:
        if use_cache and (cached := cache_get(JURISDICTION_CACHE_KEY)):
            return cached

        jurisdictions = list(
            self.db.execute(
                select(Jurisdiction)
                .where(Jurisdiction.is_active.is_(True))
                .order_by(Jurisdiction.code)
            )
            .scalars()
            .all()
        )
        classifications = self._latest_classifications()
        checks = self._latest_checks()
        total_live = self.db.execute(
            select(func.count()).select_from(AISystem).where(AISystem.is_deleted.is_(False))
        ).scalar_one()

        rows = []
        for jur in jurisdictions:
            jur_class = [
                c for c in classifications if c.jurisdiction_code == jur.code and c.is_applicable
            ]
            in_scope = {c.ai_system_id for c in jur_class}
            jur_checks = [c for c in checks if c.jurisdiction_code == jur.code]
            failures = [c for c in jur_checks if c.result == PolicyResult.FAIL]
            failing_systems = {c.ai_system_id for c in failures}
            checked_systems = {c.ai_system_id for c in jur_checks}

            compliant = len(checked_systems - failing_systems)
            non_compliant = len(failing_systems)
            unassessed = max(len(in_scope) - len(checked_systems), 0)
            rate = round(compliant / len(in_scope), 3) if in_scope else 0.0

            rows.append(
                {
                    "jurisdiction_code": jur.code,
                    "jurisdiction_name": jur.name,
                    "systems_in_scope": len(in_scope),
                    "compliant_systems": compliant,
                    "non_compliant_systems": non_compliant,
                    "unassessed_systems": unassessed,
                    "compliance_rate": rate,
                    "risk_tiers": self._tier_rows(Counter(str(c.risk_tier) for c in jur_class)),
                    "open_failures": len(failures),
                    "critical_failures": sum(
                        1 for c in failures if c.severity == PolicySeverity.CRITICAL
                    ),
                }
            )

        logger.debug("dashboard_by_jurisdiction_computed", systems=total_live, rows=len(rows))
        return self._cache(
            JURISDICTION_CACHE_KEY,
            {"jurisdictions": rows, "generated_at": datetime.now(UTC).isoformat()},
        )

    def recent_failures(self, *, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(PolicyCheck, AISystem.name, Policy.name)
            .join(AISystem, AISystem.id == PolicyCheck.ai_system_id)
            .join(Policy, Policy.id == PolicyCheck.policy_id)
            .where(
                PolicyCheck.result.in_([PolicyResult.FAIL, PolicyResult.ERROR]),
                AISystem.is_deleted.is_(False),
            )
            .order_by(PolicyCheck.checked_at.desc())
            .limit(limit)
        )
        return [
            {
                "check_id": str(check.id),
                "ai_system_id": str(check.ai_system_id),
                "ai_system_name": system_name,
                "policy_key": check.policy_key,
                "policy_name": policy_name,
                "jurisdiction_code": check.jurisdiction_code,
                "severity": str(check.severity),
                "result": str(check.result),
                "explanation": check.explanation,
                "checked_at": check.checked_at.isoformat(),
            }
            for check, system_name, policy_name in self.db.execute(stmt).unique().all()
        ]

    def pending_reviews(self, *, limit: int = 10, stale_days: int = 90) -> list[dict[str, Any]]:
        """Systems never classified, or whose classification predates their metadata."""
        latest_eval = (
            select(
                RiskClassification.ai_system_id.label("sid"),
                func.max(RiskClassification.evaluated_at).label("last_eval"),
                func.max(RiskClassification.metadata_version).label("eval_version"),
            )
            .group_by(RiskClassification.ai_system_id)
            .subquery()
        )
        stmt = (
            select(AISystem, latest_eval.c.last_eval, latest_eval.c.eval_version)
            .outerjoin(latest_eval, latest_eval.c.sid == AISystem.id)
            .where(AISystem.is_deleted.is_(False), AISystem.status != SystemStatus.RETIRED)
            .order_by(latest_eval.c.last_eval.asc().nulls_first())
            .limit(limit)
        )
        stale_cutoff = datetime.now(UTC) - timedelta(days=stale_days)
        rows: list[dict[str, Any]] = []
        for system, last_eval, eval_version in self.db.execute(stmt).unique().all():
            if last_eval is not None and last_eval.tzinfo is None:
                last_eval = last_eval.replace(tzinfo=UTC)
            if last_eval is None:
                reason = "Never classified"
            elif eval_version is not None and eval_version < system.metadata_version:
                reason = "Metadata changed since last classification"
            elif last_eval < stale_cutoff:
                reason = f"Classification older than {stale_days} days"
            else:
                continue
            rows.append(
                {
                    "ai_system_id": str(system.id),
                    "ai_system_name": system.name,
                    "status": str(system.status),
                    "reason": reason,
                    "last_evaluated_at": last_eval.isoformat() if last_eval else None,
                }
            )
        return rows

    # ---------- helpers ----------

    @staticmethod
    def _tier_rows(counter: Counter[str]) -> list[dict[str, Any]]:
        return [
            {"risk_tier": tier, "count": counter.get(tier, 0)}
            for tier in (
                RiskTier.PROHIBITED,
                RiskTier.HIGH,
                RiskTier.LIMITED,
                RiskTier.MINIMAL,
                RiskTier.UNKNOWN,
            )
        ]

    @staticmethod
    def _cache(key: str, value: dict[str, Any]) -> dict[str, Any]:
        cache_set(key, value)
        return value
