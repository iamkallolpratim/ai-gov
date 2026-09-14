from __future__ import annotations

from app.models.enums import RiskTier
from app.services.risk import RiskClassificationService


def test_baseline_flags_high_risk_use_case(db, high_risk_system):
    baseline = RiskClassificationService(db).baseline(high_risk_system.system_metadata)
    assert baseline["tier"] == RiskTier.HIGH
    assert any(s["signal"] == "high_risk_use_case" for s in baseline["signals"])


def test_baseline_marks_prohibited_use_case(db, high_risk_system):
    high_risk_system.system_metadata.use_case = "social_scoring"
    db.flush()
    baseline = RiskClassificationService(db).baseline(high_risk_system.system_metadata)
    assert baseline["tier"] == RiskTier.PROHIBITED
    assert baseline["score"] == 100.0


def test_baseline_minimal_for_benign_system(db, high_risk_system):
    meta = high_risk_system.system_metadata
    meta.use_case = "demand_forecasting"
    meta.makes_automated_decisions = False
    db.flush()
    baseline = RiskClassificationService(db).baseline(meta)
    assert baseline["tier"] == RiskTier.MINIMAL


def test_overlay_escalates_on_jurisdiction_rule(db, high_risk_system, eu_jurisdiction):
    service = RiskClassificationService(db)
    meta = high_risk_system.system_metadata
    meta.use_case = "demand_forecasting"
    meta.makes_automated_decisions = False
    meta.is_safety_component = True
    db.flush()

    baseline = service.baseline(meta)
    overlay = service.apply_overlay(eu_jurisdiction, baseline, meta)
    assert overlay["tier"] == RiskTier.HIGH
    assert any("escalates tier" in n for n in overlay["overlay_notes"])


def test_classify_persists_immutable_records(db, high_risk_system, eu_jurisdiction, admin_user):
    service = RiskClassificationService(db)
    assessment, classifications = service.classify(high_risk_system, actor=admin_user)

    assert list(assessment.applicable_codes) == ["EU"]
    assert len(classifications) == 1
    record = classifications[0]
    assert record.risk_tier == RiskTier.HIGH
    assert record.is_applicable is True
    assert record.details["overlay"]["obligations"] == ["Art. 14 human oversight"]
    # The applicability decision is persisted alongside the risk decision.
    assert record.details["jurisdiction"]["signals"]
    assert record.details["jurisdiction"]["evaluation_order"] == ["EU"]

    # Re-running appends rather than overwriting.
    service.classify(high_risk_system, actor=admin_user)
    assert len(service.history(high_risk_system.id)) == 2
    assert len(service.latest_for_system(high_risk_system.id)) == 1


def test_most_restrictive_tier_across_jurisdictions(
    db, high_risk_system, eu_jurisdiction, in_jurisdiction, admin_user
):
    high_risk_system.system_metadata.deployment_regions = ["EU", "IN"]
    db.flush()
    service = RiskClassificationService(db)
    assessment, classifications = service.classify(high_risk_system, actor=admin_user)
    assert service.most_restrictive_tier(classifications) == RiskTier.HIGH
    assert assessment.most_restrictive == ("EU",)
    assert assessment.apply_most_restrictive is True


def test_explicitly_requested_jurisdiction_is_recorded_as_inapplicable(
    db, high_risk_system, eu_jurisdiction, in_jurisdiction, admin_user
):
    """Asking for a regime with no nexus must still produce an auditable record."""
    service = RiskClassificationService(db)
    _, classifications = service.classify(
        high_risk_system, jurisdiction_codes=["IN"], actor=admin_user
    )
    assert [c.jurisdiction_code for c in classifications] == ["IN"]
    assert classifications[0].is_applicable is False
    assert service.most_restrictive_tier(classifications) == RiskTier.UNKNOWN
