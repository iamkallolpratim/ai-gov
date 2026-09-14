from __future__ import annotations

from app.services.dashboard import DashboardService
from app.services.policy import PolicyService
from app.services.risk import RiskClassificationService
from tests.unit.test_policy_service import FakeOPA


def test_summary_counts_and_score(db, high_risk_system, eu_jurisdiction, eu_policy, admin_user):
    PolicyService(
        db, opa=FakeOPA({"allow": False, "violations": [{"msg": "no oversight"}]})
    ).evaluate_system(high_risk_system, actor=admin_user)

    summary = DashboardService(db).summary(use_cache=False)
    assert summary["total_systems"] == 1
    assert summary["active_systems"] == 1
    assert summary["systems_assessed"] == 1
    assert summary["open_failures"] == 1
    assert summary["critical_failures"] == 1
    assert summary["overall_compliance_score"] == 0.0
    assert {t["risk_tier"]: t["count"] for t in summary["risk_tiers"]}["high"] == 1
    assert summary["recent_failures"][0]["policy_key"] == "eu_high_risk_obligations"


def test_summary_score_full_when_compliant(
    db, high_risk_system, eu_jurisdiction, eu_policy, admin_user
):
    PolicyService(db, opa=FakeOPA({"allow": True, "violations": []})).evaluate_system(
        high_risk_system, actor=admin_user
    )
    summary = DashboardService(db).summary(use_cache=False)
    assert summary["overall_compliance_score"] == 100.0
    assert summary["open_failures"] == 0


def test_by_jurisdiction_breakdown(db, high_risk_system, eu_jurisdiction, eu_policy, admin_user):
    PolicyService(db, opa=FakeOPA({"allow": False, "violations": [{"msg": "x"}]})).evaluate_system(
        high_risk_system, actor=admin_user
    )
    rows = DashboardService(db).by_jurisdiction(use_cache=False)["jurisdictions"]
    eu = next(r for r in rows if r["jurisdiction_code"] == "EU")
    assert eu["systems_in_scope"] == 1
    assert eu["non_compliant_systems"] == 1
    assert eu["compliance_rate"] == 0.0
    assert eu["critical_failures"] == 1


def test_pending_reviews_flags_unclassified(db, high_risk_system, eu_jurisdiction, admin_user):
    reviews = DashboardService(db).pending_reviews()
    assert reviews[0]["reason"] == "Never classified"

    RiskClassificationService(db).classify(high_risk_system, actor=admin_user)
    assert DashboardService(db).pending_reviews() == []

    high_risk_system.metadata_version = 2
    db.flush()
    stale = DashboardService(db).pending_reviews()
    assert stale[0]["reason"] == "Metadata changed since last classification"
