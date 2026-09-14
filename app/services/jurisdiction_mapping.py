"""Adapters between the pure jurisdiction engine and the API schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.schemas.jurisdiction import JurisdictionDetectionResult, JurisdictionMatch
from app.services.jurisdiction_engine import JurisdictionAssessment, JurisdictionVerdict


def verdict_to_match(verdict: JurisdictionVerdict) -> JurisdictionMatch:
    return JurisdictionMatch(
        code=verdict.code,
        name=verdict.name,
        regulation_name=verdict.regulation_name,
        applicable=verdict.applicable,
        confidence=verdict.confidence,
        reasons=list(verdict.reasons),
        signals=list(verdict.signals),
        matched_territories=list(verdict.matched_territories),
        strictness=verdict.strictness,
    )


def assessment_to_result(
    assessment: JurisdictionAssessment,
    ai_system_id: uuid.UUID,
    *,
    include_inapplicable: bool = True,
    evaluated_at: datetime | None = None,
) -> JurisdictionDetectionResult:
    verdicts = assessment.verdicts if include_inapplicable else assessment.applicable
    return JurisdictionDetectionResult(
        ai_system_id=ai_system_id,
        matches=[verdict_to_match(v) for v in verdicts],
        applicable_jurisdictions=list(assessment.applicable_codes),
        evaluation_order=list(assessment.evaluation_order),
        most_restrictive_jurisdictions=list(assessment.most_restrictive),
        apply_most_restrictive=assessment.apply_most_restrictive,
        conflict_notes=list(assessment.conflict_notes),
        most_restrictive=assessment.primary,
        evaluated_at=evaluated_at or datetime.now(UTC),
    )
