from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import PolicyEvaluationError
from app.models.enums import PolicyResult
from app.services.policy import PolicyService


class FakeOPA:
    """Stands in for a live OPA server."""

    def __init__(self, result: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.result = result
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def evaluate(self, package: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((package, input_doc))
        if self.fail:
            raise PolicyEvaluationError("OPA unreachable")
        return {"result": self.result}

    def upsert_policy(self, policy_id: str, rego_code: str) -> None:  # pragma: no cover
        pass

    def health(self) -> bool:  # pragma: no cover
        return not self.fail


def test_opa_pass_produces_pass_check(db, high_risk_system, eu_jurisdiction, eu_policy, admin_user):
    opa = FakeOPA({"allow": True, "violations": []})
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    assert len(checks) == 1
    assert checks[0].result == PolicyResult.PASS
    assert checks[0].engine == "opa"
    assert opa.calls[0][0] == "aigov.eu.high_risk"


def test_opa_denial_produces_fail_with_remediation(
    db, high_risk_system, eu_jurisdiction, eu_policy, admin_user
):
    opa = FakeOPA(
        {
            "allow": False,
            "violations": [
                {
                    "rule": "art_14",
                    "msg": "Human oversight is not documented.",
                    "remediation": "Document oversight measures.",
                }
            ],
        }
    )
    checks = PolicyService(db, opa=opa).evaluate_system(high_risk_system, actor=admin_user)

    check = checks[0]
    assert check.result == PolicyResult.FAIL
    assert "Human oversight is not documented." in check.explanation
    assert check.remediation == ["Document oversight measures."]
    assert check.violations[0]["rule"] == "art_14"


def test_falls_back_to_declarative_rules_when_opa_down(
    db, high_risk_system, eu_jurisdiction, eu_policy, admin_user
):
    checks = PolicyService(db, opa=FakeOPA(fail=True)).evaluate_system(
        high_risk_system, actor=admin_user
    )
    check = checks[0]
    assert check.engine == "rules"
    assert check.result == PolicyResult.FAIL
    fields = {v["field"] for v in check.violations}
    assert fields == {
        "human_oversight_documented",
        "conformity_assessment_done",
        "technical_documentation_url",
    }


def test_policy_skipped_when_risk_tier_does_not_match(
    db, high_risk_system, eu_jurisdiction, eu_policy, admin_user
):
    meta = high_risk_system.system_metadata
    meta.use_case = "demand_forecasting"
    meta.makes_automated_decisions = False
    db.flush()

    checks = PolicyService(db, opa=FakeOPA({"allow": True})).evaluate_system(
        high_risk_system, actor=admin_user
    )
    assert checks == []


def test_summarize_reports_compliance(db, high_risk_system, eu_jurisdiction, eu_policy, admin_user):
    service = PolicyService(db, opa=FakeOPA({"allow": True, "violations": []}))
    checks = service.evaluate_system(high_risk_system, actor=admin_user)
    summary = service.summarize(checks)
    assert summary == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "warnings": 0,
        "errors": 0,
        "compliant": True,
    }


def test_check_input_document_shape(db, high_risk_system, eu_jurisdiction, eu_policy):
    service = PolicyService(db, opa=FakeOPA({"allow": True}))
    doc = service.build_input(high_risk_system, "EU", "high")
    assert doc["jurisdiction"] == "EU"
    assert doc["risk_tier"] == "high"
    assert doc["metadata"]["use_case"] == "employment_screening"
    assert doc["system"]["name"] == "Resume Screener"


def test_error_result_when_no_rego_and_no_rules(
    db, high_risk_system, eu_jurisdiction, eu_policy, admin_user
):
    eu_policy.rules = {}
    db.flush()
    checks = PolicyService(db, opa=FakeOPA(fail=True)).evaluate_system(
        high_risk_system, actor=admin_user
    )
    assert checks[0].result == PolicyResult.ERROR
    assert checks[0].engine == "none"


@pytest.mark.parametrize("reclassify", [True, False])
def test_batch_evaluation(db, high_risk_system, eu_jurisdiction, eu_policy, admin_user, reclassify):
    service = PolicyService(db, opa=FakeOPA({"allow": True}))
    if not reclassify:
        service.risk_service.classify(high_risk_system, actor=admin_user)
    results = service.evaluate_batch([high_risk_system], reclassify=reclassify, actor=admin_user)
    assert set(results) == {high_risk_system.id}
