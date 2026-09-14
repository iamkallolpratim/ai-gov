"""RiskClassificationService: global baseline scoring + regional overlays.

Baseline produces signals and a 0-100 score from system metadata. Each jurisdiction's
``risk_taxonomy`` then maps those signals onto its own tier vocabulary (e.g. the EU AI
Act's prohibited / high-risk / limited / minimal ladder). Classifications are
append-only: every run writes a new immutable row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.ai_system import AISystem, SystemMetadata
from app.models.enums import RISK_TIER_ORDER, AuditAction, RiskTier
from app.models.jurisdiction import Jurisdiction
from app.models.risk import RiskClassification
from app.models.user import User
from app.services.audit import record_audit
from app.services.jurisdiction_engine import (
    JurisdictionAssessment,
    JurisdictionVerdict,
    SystemProfile,
    load_engine,
)

logger = get_logger(__name__)

# Baseline signal -> (weight, human-readable rationale).
BASELINE_SIGNALS: dict[str, tuple[float, str]] = {
    "uses_biometrics": (25.0, "Processes biometric identifiers"),
    "is_safety_component": (25.0, "Acts as a safety component of a product"),
    "makes_automated_decisions": (15.0, "Makes automated decisions about individuals"),
    "affects_minors": (15.0, "Affects minors"),
    "uses_generative_ai": (5.0, "Generates synthetic content"),
}

AUTONOMY_WEIGHT = {
    "fully_autonomous": 20.0,
    "human_on_the_loop": 10.0,
    "human_in_the_loop": 0.0,
}

# Use cases treated as high-risk in the global baseline (EU AI Act Annex III shaped).
HIGH_RISK_USE_CASES = {
    "employment_screening",
    "credit_scoring",
    "biometric_identification",
    "law_enforcement",
    "critical_infrastructure",
    "education_assessment",
    "migration_asylum",
    "essential_services",
    "medical_diagnosis",
}

PROHIBITED_USE_CASES = {
    "social_scoring",
    "emotion_recognition_workplace",
    "predictive_policing_individual",
    "untargeted_face_scraping",
    "subliminal_manipulation",
}

SENSITIVE_DATA_CATEGORIES = {"biometric", "health", "genetic", "criminal", "children"}


class RiskClassificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        # The engine itself is pure; loading it is the one query it costs.
        self.jurisdiction_engine = load_engine(db)

    # ---------- baseline ----------

    def baseline(self, meta: SystemMetadata | None) -> dict[str, Any]:
        signals: list[dict[str, Any]] = []
        score = 0.0

        if meta is None:
            return {
                "score": 0.0,
                "signals": [],
                "tier": RiskTier.UNKNOWN,
                "use_case": None,
                "notes": ["No structured metadata recorded; classification is indicative only."],
            }

        for field, (weight, rationale) in BASELINE_SIGNALS.items():
            if bool(getattr(meta, field, False)):
                score += weight
                signals.append({"signal": field, "weight": weight, "rationale": rationale})

        autonomy = str(meta.autonomy_level)
        autonomy_weight = AUTONOMY_WEIGHT.get(autonomy, 0.0)
        if autonomy_weight:
            score += autonomy_weight
            signals.append(
                {
                    "signal": "autonomy_level",
                    "weight": autonomy_weight,
                    "rationale": f"Autonomy level is {autonomy}",
                }
            )

        sensitive = {c.lower() for c in (meta.data_categories or [])} & SENSITIVE_DATA_CATEGORIES
        if sensitive:
            score += 15.0
            signals.append(
                {
                    "signal": "sensitive_data",
                    "weight": 15.0,
                    "rationale": f"Processes sensitive data categories: {sorted(sensitive)}",
                }
            )

        use_case = (meta.use_case or "").lower()
        if use_case in PROHIBITED_USE_CASES:
            tier = RiskTier.PROHIBITED
            score = 100.0
            signals.append(
                {
                    "signal": "prohibited_use_case",
                    "weight": 100.0,
                    "rationale": f"Use case '{use_case}' is on the prohibited-practices list",
                }
            )
        elif use_case in HIGH_RISK_USE_CASES:
            score += 30.0
            signals.append(
                {
                    "signal": "high_risk_use_case",
                    "weight": 30.0,
                    "rationale": f"Use case '{use_case}' is an enumerated high-risk application",
                }
            )
            tier = RiskTier.HIGH
        else:
            tier = self._tier_from_score(score)

        score = min(round(score, 2), 100.0)
        if tier not in (RiskTier.PROHIBITED, RiskTier.HIGH):
            tier = self._tier_from_score(score)

        return {
            "score": score,
            "signals": signals,
            "tier": tier,
            "use_case": use_case or None,
            "notes": [],
        }

    @staticmethod
    def _tier_from_score(score: float) -> RiskTier:
        if score >= 100.0:
            return RiskTier.PROHIBITED
        if score >= 50.0:
            return RiskTier.HIGH
        if score >= 20.0:
            return RiskTier.LIMITED
        return RiskTier.MINIMAL

    # ---------- overlays ----------

    def apply_overlay(
        self, jurisdiction: Jurisdiction, baseline: dict[str, Any], meta: SystemMetadata | None
    ) -> dict[str, Any]:
        """Adjust the baseline tier/score using a jurisdiction's taxonomy overlay."""
        taxonomy: dict[str, Any] = jurisdiction.risk_taxonomy or {}
        tier = RiskTier(str(baseline["tier"]))
        score = float(baseline["score"])
        overlay_notes: list[str] = []

        use_case = baseline.get("use_case")
        if use_case:
            if use_case in {u.lower() for u in taxonomy.get("prohibited_use_cases", [])}:
                tier = RiskTier.PROHIBITED
                score = 100.0
                overlay_notes.append(
                    f"{jurisdiction.code}: use case '{use_case}' is prohibited in this jurisdiction"
                )
            elif use_case in {u.lower() for u in taxonomy.get("high_risk_use_cases", [])}:
                tier = self._escalate(tier, RiskTier.HIGH)
                score = max(score, 60.0)
                overlay_notes.append(
                    f"{jurisdiction.code}: use case '{use_case}' is classified high-risk"
                )

        for field, target in (taxonomy.get("escalate_if") or {}).items():
            if meta is not None and bool(getattr(meta, field, False)):
                target_tier = RiskTier(str(target))
                if RISK_TIER_ORDER[target_tier] > RISK_TIER_ORDER[tier]:
                    tier = target_tier
                    score = max(score, 60.0 if target_tier == RiskTier.HIGH else score)
                overlay_notes.append(f"{jurisdiction.code}: '{field}' escalates tier to {target}")

        minimum = taxonomy.get("minimum_tier")
        if minimum:
            tier = self._escalate(tier, RiskTier(str(minimum)))
            overlay_notes.append(f"{jurisdiction.code}: minimum tier floor is {minimum}")

        multiplier = float(taxonomy.get("score_multiplier", 1.0))
        score = min(round(score * multiplier, 2), 100.0)

        return {
            "tier": tier,
            "score": score,
            "overlay_notes": overlay_notes,
            "tier_label": (taxonomy.get("tier_labels") or {}).get(str(tier), str(tier)),
            "obligations": (taxonomy.get("obligations") or {}).get(str(tier), []),
        }

    @staticmethod
    def _escalate(current: RiskTier, candidate: RiskTier) -> RiskTier:
        return candidate if RISK_TIER_ORDER[candidate] > RISK_TIER_ORDER[current] else current

    # ---------- persistence ----------

    def classify(
        self,
        system: AISystem,
        *,
        jurisdiction_codes: list[str] | None = None,
        actor: User | None = None,
    ) -> tuple[JurisdictionAssessment, list[RiskClassification]]:
        """Detect applicable regimes, then write one immutable classification per regime.

        ``jurisdiction_codes`` narrows the run to specific regimes. A code with no
        detected nexus is still classified, flagged ``is_applicable=False``, so an
        explicit "assess us against China anyway" request is recorded rather than
        silently dropped.
        """
        assessment = self.jurisdiction_engine.evaluate(SystemProfile.from_system(system))
        verdicts: list[JurisdictionVerdict] = list(assessment.applicable)

        if jurisdiction_codes:
            wanted = {c.upper() for c in jurisdiction_codes}
            verdicts = [v for v in verdicts if v.code.upper() in wanted]
            known = {v.code.upper() for v in verdicts}
            by_code = {v.code.upper(): v for v in assessment.verdicts}
            for code in sorted(wanted - known):
                jur = self._get_jurisdiction(code)
                evaluated = by_code.get(code.upper())
                verdicts.append(
                    JurisdictionVerdict(
                        code=jur.code,
                        name=jur.name,
                        regulation_name=jur.regulation_name,
                        applicable=False,
                        confidence=0.0,
                        reasons=(
                            evaluated.reasons
                            if evaluated
                            else ("Explicitly requested; no automatic nexus detected",)
                        ),
                        signals=(),
                        strictness=int((jur.overlay_config or {}).get("strictness", 50)),
                    )
                )

        baseline = self.baseline(system.system_metadata)
        classifications: list[RiskClassification] = []
        now = datetime.now(UTC)

        for verdict in verdicts:
            jur = self._get_jurisdiction(verdict.code)
            overlay = self.apply_overlay(jur, baseline, system.system_metadata)
            record = RiskClassification(
                ai_system_id=system.id,
                jurisdiction_code=jur.code,
                risk_tier=overlay["tier"],
                score=overlay["score"],
                is_applicable=verdict.applicable,
                applicability_reasons=list(verdict.reasons),
                metadata_version=system.metadata_version,
                evaluated_at=now,
                evaluated_by_id=actor.id if actor else None,
                details={
                    "baseline": {
                        "score": baseline["score"],
                        "tier": str(baseline["tier"]),
                        "signals": baseline["signals"],
                        "notes": baseline["notes"],
                    },
                    "overlay": {
                        "notes": overlay["overlay_notes"],
                        "tier_label": overlay["tier_label"],
                        "obligations": overlay["obligations"],
                    },
                    "jurisdiction": {
                        "confidence": verdict.confidence,
                        "signals": list(verdict.signals),
                        "matched_territories": list(verdict.matched_territories),
                        "strictness": verdict.strictness,
                        "evaluation_order": list(assessment.evaluation_order),
                        "most_restrictive": list(assessment.most_restrictive),
                        "apply_most_restrictive": assessment.apply_most_restrictive,
                    },
                    "engine_version": "2.0.0",
                },
            )
            self.db.add(record)
            classifications.append(record)

        self.db.flush()
        record_audit(
            self.db,
            resource_type="ai_system",
            resource_id=system.id,
            action=AuditAction.CLASSIFY,
            actor=actor,
            new_values={
                c.jurisdiction_code: {"tier": str(c.risk_tier), "score": c.score}
                for c in classifications
            },
        )
        logger.info(
            "system_classified",
            ai_system_id=str(system.id),
            results={c.jurisdiction_code: str(c.risk_tier) for c in classifications},
        )
        return assessment, classifications

    def latest_for_system(self, system_id: uuid.UUID) -> dict[str, RiskClassification]:
        """Most recent classification per jurisdiction."""
        stmt = (
            select(RiskClassification)
            .where(RiskClassification.ai_system_id == system_id)
            .order_by(RiskClassification.evaluated_at.desc())
        )
        latest: dict[str, RiskClassification] = {}
        for row in self.db.execute(stmt).scalars().all():
            latest.setdefault(row.jurisdiction_code, row)
        return latest

    def history(
        self, system_id: uuid.UUID, *, jurisdiction_code: str | None = None
    ) -> list[RiskClassification]:
        stmt = select(RiskClassification).where(RiskClassification.ai_system_id == system_id)
        if jurisdiction_code:
            stmt = stmt.where(RiskClassification.jurisdiction_code == jurisdiction_code.upper())
        stmt = stmt.order_by(RiskClassification.evaluated_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    @staticmethod
    def most_restrictive_tier(classifications: list[RiskClassification]) -> RiskTier:
        applicable = [c for c in classifications if c.is_applicable]
        if not applicable:
            return RiskTier.UNKNOWN
        return max(applicable, key=lambda c: RISK_TIER_ORDER[RiskTier(str(c.risk_tier))]).risk_tier

    def _get_jurisdiction(self, code: str) -> Jurisdiction:
        jur = self.db.execute(
            select(Jurisdiction).where(Jurisdiction.code == code.upper())
        ).scalar_one_or_none()
        if jur is None:
            raise NotFoundError(f"Jurisdiction '{code}' is not registered.")
        return jur
