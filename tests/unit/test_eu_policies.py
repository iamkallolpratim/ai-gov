"""EU AI Act policy evaluation through PolicyService.

These run against a faked OPA that returns the same document shape the real EU
packages emit, so they exercise the service's interpretation logic without needing
a server. `tests/integration/test_opa_live.py` runs the same scenarios through a
real OPA instance and verifies the Rego itself.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.models.enums import PolicyResult, PolicySeverity
from app.services.policy import PolicyService
from tests.conftest_policies import make_policies


class ScriptedOPA:
    """Returns a canned package document, in the real EU result shape."""

    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def evaluate(self, package: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((package, input_doc))
        return {"result": self.documents.get(package, allow_document())}

    def upsert_policy(self, policy_id: str, rego_code: str) -> None:  # pragma: no cover
        pass

    def health(self) -> bool:  # pragma: no cover
        return True


def allow_document(in_scope: bool = True) -> dict[str, Any]:
    return {
        "allow": True,
        "decision": "allow",
        "in_scope": in_scope,
        "rule_ids": [],
        "severity": "none",
        "violations": [],
    }


def deny_document(*violations: dict[str, Any]) -> dict[str, Any]:
    return {
        "allow": False,
        "decision": "deny",
        "in_scope": True,
        "rule_ids": sorted(v["rule_id"] for v in violations),
        "severity": violations[0]["severity"],
        "violations": list(violations),
    }


OVERSIGHT_VIOLATION = {
    "rule_id": "eu.high_risk.art_14.human_oversight_missing",
    "article": "Art. 14",
    "severity": "critical",
    "msg": "No human oversight measures are documented. Art. 14 requires high-risk "
    "systems to be designed so that natural persons can effectively oversee them.",
    "remediation": "Assign named oversight roles and set 'human_oversight_documented' to true.",
}

LOGGING_VIOLATION = {
    "rule_id": "eu.high_risk.art_12.record_keeping",
    "article": "Art. 12",
    "severity": "high",
    "msg": "Automatic event logging is not enabled.",
    "remediation": "Enable automatic logging and retain logs for six months.",
}

ACCESSIBILITY_VIOLATION = {
    "rule_id": "eu.transparency.art_50_5.accessible_format",
    "article": "Art. 50(5)",
    "severity": "low",
    "msg": "Transparency notices are owed but no accessible format is recorded.",
    "remediation": "Provide disclosures in an accessible format.",
}


@pytest.fixture
def eu_policies(db, eu_jurisdiction):
    return make_policies(db)


def test_high_risk_employment_system_fails_with_structured_findings(
    db, high_risk_system, eu_policies, admin_user
):
    opa = ScriptedOPA({"aigov.eu.high_risk": deny_document(OVERSIGHT_VIOLATION, LOGGING_VIOLATION)})
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    high_risk = next(c for c in checks if c.policy_key == "eu_ai_act_high_risk")
    assert high_risk.result == PolicyResult.FAIL
    assert high_risk.severity == PolicySeverity.CRITICAL

    # Everything the console needs to render a finding is present per violation.
    by_rule = {v["rule_id"]: v for v in high_risk.violations}
    assert set(by_rule) == {
        "eu.high_risk.art_14.human_oversight_missing",
        "eu.high_risk.art_12.record_keeping",
    }
    oversight = by_rule["eu.high_risk.art_14.human_oversight_missing"]
    assert oversight["article"] == "Art. 14"
    assert oversight["severity"] == "critical"
    assert "Art. 14" in oversight["msg"]
    assert oversight["remediation"]
    assert "[Art. 14]" in high_risk.explanation


def test_low_risk_internal_tool_passes(db, high_risk_system, eu_policies, admin_user):
    meta = high_risk_system.system_metadata
    meta.use_case = "demand_forecasting"
    meta.makes_automated_decisions = False
    db.flush()

    # Out of scope for the high-risk package; the other packages find nothing.
    opa = ScriptedOPA(
        {
            "aigov.eu.high_risk": allow_document(in_scope=False),
            "aigov.eu.prohibited": allow_document(),
            "aigov.eu.transparency": allow_document(),
        }
    )
    service = PolicyService(db, opa=opa)
    checks = service.evaluate_system(high_risk_system, actor=admin_user)

    assert all(c.result == PolicyResult.PASS for c in checks)
    assert service.summarize(checks)["compliant"] is True
    # The high-risk policy is tier-gated, so it is not even selected for a minimal system.
    assert "eu_ai_act_high_risk" not in {c.policy_key for c in checks}


def test_biometric_system_fails_prohibited_practices(db, high_risk_system, eu_policies, admin_user):
    meta = high_risk_system.system_metadata
    meta.use_case = "biometric_identification"
    meta.uses_biometrics = True
    meta.data_categories = ["biometric"]
    meta.attributes = {"realtime_identification": True, "publicly_accessible_space": True}
    db.flush()

    violation = {
        "rule_id": "eu.prohibited.art_5_1_h.realtime_biometric_id",
        "article": "Art. 5(1)(h)",
        "severity": "critical",
        "msg": "Real-time remote biometric identification without prior authorisation.",
        "remediation": "Suspend deployment until a prior authorisation is recorded.",
    }
    opa = ScriptedOPA({"aigov.eu.prohibited": deny_document(violation)})
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    prohibited = next(c for c in checks if c.policy_key == "eu_ai_act_prohibited")
    assert prohibited.result == PolicyResult.FAIL
    assert prohibited.severity == PolicySeverity.CRITICAL
    assert prohibited.violations[0]["article"] == "Art. 5(1)(h)"


def test_missing_human_oversight_is_a_critical_failure(
    db, high_risk_system, eu_policies, admin_user
):
    opa = ScriptedOPA({"aigov.eu.high_risk": deny_document(OVERSIGHT_VIOLATION)})
    service = PolicyService(db, opa=opa)
    checks = service.evaluate_system(high_risk_system, actor=admin_user)

    summary = service.summarize(checks)
    assert summary["failed"] >= 1
    assert summary["compliant"] is False
    oversight = next(c for c in checks if any("art_14" in v["rule_id"] for v in c.violations))
    assert oversight.result == PolicyResult.FAIL
    assert oversight.remediation


def test_out_of_scope_package_is_a_pass_not_a_silent_success(
    db, high_risk_system, eu_policies, admin_user
):
    opa = ScriptedOPA({"aigov.eu.high_risk": allow_document(in_scope=False)})
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    high_risk = next(c for c in checks if c.policy_key == "eu_ai_act_high_risk")
    assert high_risk.result == PolicyResult.PASS
    assert "not applicable" in high_risk.explanation


def test_low_severity_finding_downgrades_to_warning(db, high_risk_system, eu_policies, admin_user):
    """A `medium` policy that raises only a `low` finding must warn, not fail."""
    opa = ScriptedOPA({"aigov.eu.transparency": deny_document(ACCESSIBILITY_VIOLATION)})
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    transparency = next(c for c in checks if c.policy_key == "eu_ai_act_transparency")
    assert transparency.result == PolicyResult.WARNING
    assert transparency.severity == PolicySeverity.LOW


def test_check_severity_reflects_the_worst_finding(db, high_risk_system, eu_policies, admin_user):
    opa = ScriptedOPA(
        {"aigov.eu.transparency": deny_document(ACCESSIBILITY_VIOLATION, LOGGING_VIOLATION)}
    )
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    transparency = next(c for c in checks if c.policy_key == "eu_ai_act_transparency")
    # Policy is registered `medium`; the worst finding is `high`, so the check is high.
    assert transparency.severity == PolicySeverity.HIGH
    assert transparency.result == PolicyResult.FAIL


def test_violation_without_severity_inherits_the_policy_severity(
    db, high_risk_system, eu_policies, admin_user
):
    bare = {"msg": "Something is wrong."}
    opa = ScriptedOPA(
        {
            "aigov.eu.high_risk": {
                "allow": False,
                "violations": [bare],
            }
        }
    )
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)
    high_risk = next(c for c in checks if c.policy_key == "eu_ai_act_high_risk")
    violation = high_risk.violations[0]
    assert violation["severity"] == "critical"  # from the policy row
    assert violation["rule_id"] == "eu_ai_act_high_risk"
    assert violation["remediation"]


def test_input_document_carries_everything_the_rego_reads(db, high_risk_system, eu_policies):
    opa = ScriptedOPA({})
    service = PolicyService(db, opa=opa)
    doc = service.build_input(high_risk_system, "EU", "high")

    for key in (
        "use_case",
        "autonomy_level",
        "data_categories",
        "third_party_models",
        "human_oversight_documented",
        "conformity_assessment_done",
        "training_data_documented",
        "technical_documentation_url",
        "incident_response_plan",
        "attributes",
    ):
        assert key in doc["metadata"], key
    assert doc["jurisdiction"] == "EU"
    assert doc["risk_tier"] == "high"
