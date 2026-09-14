"""End-to-end EU policy evaluation against a real OPA server.

Skipped unless an OPA instance is reachable, so the suite still runs without Docker:

    opa run --server --addr localhost:8181 policies/

These tests are the ones that actually validate the Rego. The Rego's own unit tests
live beside it (`opa test policies/`); this module verifies the whole path —
PolicyService builds the input, OPA decides, and the service turns the decision back
into an auditable PolicyCheck row.
"""

from __future__ import annotations

import pytest

from app.models.enums import PolicyResult, PolicySeverity
from app.services.opa import OPAClient
from app.services.policy import PolicyService
from tests.conftest_policies import make_policies

pytestmark = pytest.mark.opa

OPA_URL = "http://localhost:8181"


@pytest.fixture(scope="module")
def opa() -> OPAClient:
    client = OPAClient(base_url=OPA_URL)
    if not client.health():
        pytest.skip(f"No OPA server at {OPA_URL}")
    return client


@pytest.fixture
def eu_policies(db, eu_jurisdiction):
    return make_policies(db)


def compliant_metadata(system) -> None:
    """Bring a system up to full Chapter III compliance."""
    meta = system.system_metadata
    meta.human_oversight_documented = True
    meta.conformity_assessment_done = True
    meta.training_data_documented = True
    meta.incident_response_plan = True
    meta.technical_documentation_url = "https://docs.example.com/annex-iv"
    meta.third_party_models = []
    meta.attributes = {
        "risk_management_system": True,
        "automatic_logging_enabled": True,
        "instructions_for_use": True,
        "accuracy_metrics_declared": True,
        "eu_database_registered": True,
        "post_market_monitoring_plan": True,
        "human_review_of_individual_decisions": True,
        "ai_interaction_disclosed": True,
        "synthetic_content_marked": True,
        "accessible_disclosures": True,
    }


def run(db, system, opa, actor) -> dict[str, object]:
    checks = PolicyService(db, opa=opa).evaluate_system(system, actor=actor)
    return {c.policy_key: c for c in checks}


def test_undocumented_employment_system_fails_high_risk(
    db, high_risk_system, eu_policies, admin_user, opa
):
    checks = run(db, high_risk_system, opa, admin_user)
    high_risk = checks["eu_ai_act_high_risk"]

    assert high_risk.engine == "opa"
    assert high_risk.result == PolicyResult.FAIL
    assert high_risk.severity == PolicySeverity.CRITICAL

    rule_ids = {v["rule_id"] for v in high_risk.violations}
    assert "eu.high_risk.art_14.human_oversight_missing" in rule_ids
    assert "eu.high_risk.art_43.conformity_assessment" in rule_ids
    assert "eu.high_risk.art_11.technical_documentation" in rule_ids
    assert "eu.high_risk.art_9.risk_management_system" in rule_ids
    # Annex III membership is cited back to the user.
    assert any("Annex III(4)" in v["msg"] for v in high_risk.violations)


def test_fully_documented_employment_system_passes(
    db, high_risk_system, eu_policies, admin_user, opa
):
    compliant_metadata(high_risk_system)
    db.flush()

    checks = run(db, high_risk_system, opa, admin_user)
    assert checks["eu_ai_act_high_risk"].result == PolicyResult.PASS
    assert checks["eu_ai_act_prohibited"].result == PolicyResult.PASS


def test_low_risk_internal_tool_is_out_of_scope(db, high_risk_system, eu_policies, admin_user, opa):
    meta = high_risk_system.system_metadata
    meta.use_case = "demand_forecasting"
    meta.makes_automated_decisions = False
    meta.uses_generative_ai = False
    db.flush()

    checks = run(db, high_risk_system, opa, admin_user)
    # Tier-gated out of the high-risk policy entirely.
    assert "eu_ai_act_high_risk" not in checks
    assert checks["eu_ai_act_prohibited"].result == PolicyResult.PASS
    assert checks["eu_ai_act_transparency"].result == PolicyResult.PASS


def test_missing_human_oversight_alone_fails(db, high_risk_system, eu_policies, admin_user, opa):
    compliant_metadata(high_risk_system)
    high_risk_system.system_metadata.human_oversight_documented = False
    db.flush()

    high_risk = run(db, high_risk_system, opa, admin_user)["eu_ai_act_high_risk"]
    rule_ids = {v["rule_id"] for v in high_risk.violations}
    assert rule_ids == {"eu.high_risk.art_14.human_oversight_missing"}
    assert high_risk.result == PolicyResult.FAIL
    assert high_risk.remediation


def test_fully_autonomous_without_override_fails_oversight(
    db, high_risk_system, eu_policies, admin_user, opa
):
    compliant_metadata(high_risk_system)
    high_risk_system.system_metadata.autonomy_level = "fully_autonomous"
    db.flush()

    high_risk = run(db, high_risk_system, opa, admin_user)["eu_ai_act_high_risk"]
    rule_ids = {v["rule_id"] for v in high_risk.violations}
    assert "eu.high_risk.art_14.oversight_not_effective" in rule_ids


def test_biometric_system_fails_prohibited_and_high_risk(
    db, high_risk_system, eu_policies, admin_user, opa
):
    compliant_metadata(high_risk_system)
    meta = high_risk_system.system_metadata
    meta.use_case = "biometric_identification"
    meta.uses_biometrics = True
    meta.industry = "law_enforcement"
    meta.data_categories = ["biometric"]
    meta.attributes = {
        **meta.attributes,
        "realtime_identification": True,
        "publicly_accessible_space": True,
    }
    db.flush()

    checks = run(db, high_risk_system, opa, admin_user)

    prohibited = checks["eu_ai_act_prohibited"]
    assert prohibited.result == PolicyResult.FAIL
    assert "eu.prohibited.art_5_1_h.realtime_biometric_id" in {
        v["rule_id"] for v in prohibited.violations
    }

    # Biometrics also pulls in the Art. 15(5) robustness duty.
    high_risk = checks["eu_ai_act_high_risk"]
    assert "eu.high_risk.art_15.robustness_testing" in {v["rule_id"] for v in high_risk.violations}


def test_special_category_data_requires_safeguards(
    db, high_risk_system, eu_policies, admin_user, opa
):
    compliant_metadata(high_risk_system)
    high_risk_system.system_metadata.data_categories = ["personal_data", "health"]
    db.flush()

    high_risk = run(db, high_risk_system, opa, admin_user)["eu_ai_act_high_risk"]
    violation = next(
        v
        for v in high_risk.violations
        if v["rule_id"] == "eu.high_risk.art_10_5.special_category_safeguards"
    )
    assert violation["severity"] == "critical"
    assert "health" in violation["msg"]


def test_social_scoring_is_prohibited(db, high_risk_system, eu_policies, admin_user, opa):
    compliant_metadata(high_risk_system)
    high_risk_system.system_metadata.use_case = "social_scoring"
    db.flush()

    prohibited = run(db, high_risk_system, opa, admin_user)["eu_ai_act_prohibited"]
    assert prohibited.result == PolicyResult.FAIL
    assert "eu.prohibited.art_5_1_c.social_scoring" in {v["rule_id"] for v in prohibited.violations}


def test_generative_system_owes_transparency_duties(
    db, high_risk_system, eu_policies, admin_user, opa
):
    compliant_metadata(high_risk_system)
    meta = high_risk_system.system_metadata
    meta.use_case = "customer_support"
    meta.uses_generative_ai = True
    meta.attributes = {k: v for k, v in meta.attributes.items() if k != "synthetic_content_marked"}
    db.flush()

    transparency = run(db, high_risk_system, opa, admin_user)["eu_ai_act_transparency"]
    assert transparency.result == PolicyResult.FAIL
    assert "eu.transparency.art_50_2.synthetic_content_marking" in {
        v["rule_id"] for v in transparency.violations
    }


def test_raw_opa_response_is_retained_for_audit(db, high_risk_system, eu_policies, admin_user, opa):
    high_risk = run(db, high_risk_system, opa, admin_user)["eu_ai_act_high_risk"]
    raw = high_risk.raw_opa_response["result"]
    assert raw["decision"] == "deny"
    assert raw["in_scope"] is True
    assert raw["rule_ids"]
