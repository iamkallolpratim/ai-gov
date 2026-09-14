"""JurisdictionEngine.

Everything here except the last section runs on plain dataclasses — no database, no
fixtures, no I/O — because the engine is pure by construction.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.services.jurisdiction_engine import (
    DEFAULT_CONSEQUENTIAL_USE_CASES,
    DEFAULT_RULES,
    TRIGGER_REGISTRY,
    JurisdictionEngine,
    JurisdictionRule,
    SystemProfile,
    TriggerKind,
    rules_from_jurisdiction_rows,
)
from app.services.regions import normalize_regions


@pytest.fixture
def engine() -> JurisdictionEngine:
    return JurisdictionEngine()


def profile(**kwargs: object) -> SystemProfile:
    """Build a profile, normalising any region set passed as a plain list."""
    region_fields = {
        "deployment_regions",
        "data_subject_regions",
        "data_residency_regions",
        "offered_in_regions",
        "service_accessible_regions",
        "content_accessible_regions",
    }
    normalized = {
        k: (normalize_regions(v) if k in region_fields else v)  # type: ignore[arg-type]
        for k, v in kwargs.items()
    }
    return SystemProfile(**normalized)  # type: ignore[arg-type]


def codes(engine: JurisdictionEngine, p: SystemProfile) -> list[str]:
    """Applicable codes, excluding the always-on GLOBAL baseline."""
    return [c for c in engine.evaluate(p).applicable_codes if c != "GLOBAL"]


def reasons_for(engine: JurisdictionEngine, p: SystemProfile, code: str) -> list[str]:
    return [r for v in engine.evaluate(p).verdicts if v.code == code for r in v.reasons]


def signals_for(engine: JurisdictionEngine, p: SystemProfile, code: str) -> set[str]:
    return {s for v in engine.evaluate(p).verdicts if v.code == code for s in v.signals}


# ---------------------------------------------------------------------------
# Rule 1 — European Union
# ---------------------------------------------------------------------------


class TestEuropeanUnion:
    def test_deployment_in_member_state(self, engine):
        assert "EU" in codes(engine, profile(deployment_regions=["DE"]))

    def test_deployment_in_group_code(self, engine):
        assert "EU" in codes(engine, profile(deployment_regions=["EU"]))

    def test_eea_only_state_counts(self, engine):
        # Norway is EEA, not EU: the AI Act reaches it through the EEA agreement.
        assert "EU" in codes(engine, profile(deployment_regions=["NO"]))

    def test_data_subjects_in_eu_without_eu_deployment(self, engine):
        p = profile(deployment_regions=["US-NY"], data_subject_regions=["FR"])
        assert "EU" in codes(engine, p)
        assert any("Data subjects located in FR" in r for r in reasons_for(engine, p, "EU"))

    def test_offered_to_eu_users(self, engine):
        p = profile(deployment_regions=["US-NY"], offered_in_regions=["EU"])
        assert "EU" in codes(engine, p)
        assert any("Offered to users in EU" in r for r in reasons_for(engine, p, "EU"))

    def test_no_eu_nexus(self, engine):
        p = profile(deployment_regions=["BR"], data_subject_regions=["BR"])
        assert "EU" not in codes(engine, p)

    def test_biometrics_alone_does_not_pull_in_the_eu(self, engine):
        # Regression guard: an amplifier must never establish jurisdiction on its own.
        p = profile(
            deployment_regions=["US-NY"], data_subject_regions=["US-NY"], uses_biometrics=True
        )
        assert "EU" not in codes(engine, p)

    def test_biometrics_is_recorded_once_the_eu_already_applies(self, engine):
        p = profile(deployment_regions=["DE"], uses_biometrics=True)
        assert "biometric_processing" in signals_for(engine, p, "EU")


# ---------------------------------------------------------------------------
# Rule 2 — California
# ---------------------------------------------------------------------------


class TestCalifornia:
    def test_deployment_in_california(self, engine):
        assert "CA" in codes(engine, profile(deployment_regions=["US-CA"]))

    def test_spelled_out_california(self, engine):
        assert "CA" in codes(engine, profile(deployment_regions=["California"]))

    def test_users_in_california(self, engine):
        assert "CA" in codes(engine, profile(offered_in_regions=["US-CA"]))

    def test_consequential_decisions_about_californians(self, engine):
        p = profile(
            deployment_regions=["US-NY"],
            data_subject_regions=["US-CA"],
            use_case="credit_scoring",
            makes_automated_decisions=True,
        )
        assert "CA" in codes(engine, p)
        assert "consequential_decision_nexus" in signals_for(engine, p, "CA")

    def test_non_consequential_automated_decisions_need_another_nexus(self, engine):
        p = profile(
            deployment_regions=["US-NY"],
            data_subject_regions=["US-NY"],
            use_case="content_ranking",
            makes_automated_decisions=True,
        )
        assert "CA" not in codes(engine, p)

    def test_consequential_use_case_without_automation_is_not_a_nexus(self, engine):
        p = profile(
            deployment_regions=["US-NY"],
            use_case="credit_scoring",
            makes_automated_decisions=False,
        )
        assert "CA" not in codes(engine, p)

    def test_us_deployment_outside_california_is_not_enough(self, engine):
        assert "CA" not in codes(engine, profile(deployment_regions=["US-TX"]))


# ---------------------------------------------------------------------------
# Rule 3 — China
# ---------------------------------------------------------------------------


class TestChina:
    def test_service_accessible_in_china(self, engine):
        p = profile(deployment_regions=["US-NY"], service_accessible_regions=["CN"])
        assert "CN" in codes(engine, p)
        assert "service_accessibility_nexus" in signals_for(engine, p, "CN")

    def test_public_internet_reaches_china(self, engine):
        p = profile(deployment_regions=["EU"], service_accessible_regions=["GLOBAL"])
        assert "CN" in codes(engine, p)

    def test_data_processed_in_china(self, engine):
        p = profile(deployment_regions=["US-NY"], data_residency_regions=["CN"])
        assert "CN" in codes(engine, p)
        assert any("Data processed or stored in CN" in r for r in reasons_for(engine, p, "CN"))

    def test_generated_content_accessible_from_china(self, engine):
        p = profile(
            deployment_regions=["US-NY"],
            content_accessible_regions=["CN"],
            uses_generative_ai=True,
        )
        assert "CN" in codes(engine, p)
        assert "generated_content_accessibility_nexus" in signals_for(engine, p, "CN")

    def test_content_accessibility_only_counts_for_generative_systems(self, engine):
        p = profile(
            deployment_regions=["US-NY"],
            content_accessible_regions=["CN"],
            uses_generative_ai=False,
        )
        assert "CN" not in codes(engine, p)

    def test_us_only_system_stays_out_of_china(self, engine):
        p = profile(
            deployment_regions=["US-NY"],
            data_subject_regions=["US-NY"],
            service_accessible_regions=["US"],
        )
        assert "CN" not in codes(engine, p)


# ---------------------------------------------------------------------------
# Rule 4 — India
# ---------------------------------------------------------------------------


class TestIndia:
    def test_deployment_in_india(self, engine):
        assert "IN" in codes(engine, profile(deployment_regions=["IN"]))

    def test_data_subjects_in_india(self, engine):
        assert "IN" in codes(
            engine, profile(deployment_regions=["EU"], data_subject_regions=["India"])
        )

    def test_users_offered_in_india(self, engine):
        assert "IN" in codes(engine, profile(offered_in_regions=["IN"]))

    def test_no_indian_nexus(self, engine):
        assert "IN" not in codes(
            engine, profile(deployment_regions=["EU"], data_subject_regions=["EU"])
        )


# ---------------------------------------------------------------------------
# Baseline, ordering and priority
# ---------------------------------------------------------------------------


class TestBaselineAndOrdering:
    def test_global_baseline_always_applies(self, engine):
        assert "GLOBAL" in engine.evaluate(profile()).applicable_codes
        assert "GLOBAL" in engine.evaluate(profile(deployment_regions=["BR"])).applicable_codes

    def test_bare_profile_matches_only_the_baseline(self, engine):
        assert engine.evaluate(profile()).applicable_codes == ("GLOBAL",)

    def test_evaluation_order_is_strictest_first(self, engine):
        p = profile(deployment_regions=["IN", "US-CA", "DE"], data_residency_regions=["CN"])
        assert engine.evaluate(p).evaluation_order == ("EU", "CN", "CA", "IN", "GLOBAL")

    def test_most_restrictive_is_the_strictest_regime(self, engine):
        p = profile(deployment_regions=["IN", "US-CA", "DE"])
        assessment = engine.evaluate(p)
        assert assessment.most_restrictive == ("EU",)
        assert assessment.primary == "EU"
        assert engine.get_most_restrictive_jurisdictions(assessment) == ["EU"]

    def test_most_restrictive_returns_every_tied_regime(self):
        tied = JurisdictionEngine(
            [
                JurisdictionRule(
                    code="A",
                    name="A",
                    territories=frozenset({"IN"}),
                    strictness=80,
                    triggers=("deployment_nexus",),
                ),
                JurisdictionRule(
                    code="B",
                    name="B",
                    territories=frozenset({"IN"}),
                    strictness=80,
                    triggers=("deployment_nexus",),
                ),
                JurisdictionRule(
                    code="C",
                    name="C",
                    territories=frozenset({"IN"}),
                    strictness=10,
                    triggers=("deployment_nexus",),
                ),
            ]
        )
        assessment = tied.evaluate(profile(deployment_regions=["IN"]))
        assert tied.get_most_restrictive_jurisdictions(assessment) == ["A", "B"]
        assert any("equally strict" in n for n in assessment.conflict_notes)

    def test_helper_accepts_a_bare_verdict_sequence(self, engine):
        assessment = engine.evaluate(profile(deployment_regions=["DE", "IN"]))
        assert engine.get_most_restrictive_jurisdictions(list(assessment.verdicts)) == ["EU"]

    def test_most_restrictive_mode_off_for_a_single_regime(self, engine):
        # Only the GLOBAL baseline applies, so nothing can conflict.
        assessment = engine.evaluate(profile(deployment_regions=["BR"]))
        assert assessment.apply_most_restrictive is False
        assert assessment.conflict_notes == ()

    def test_most_restrictive_mode_on_for_several_regimes(self, engine):
        assessment = engine.evaluate(profile(deployment_regions=["DE", "IN"]))
        assert assessment.apply_most_restrictive is True
        assert assessment.conflict_notes

    def test_no_applicable_regime_yields_empty_priority(self):
        bare = JurisdictionEngine([r for r in DEFAULT_RULES if r.code == "EU"])
        assessment = bare.evaluate(profile(deployment_regions=["BR"]))
        assert assessment.applicable_codes == ()
        assert assessment.most_restrictive == ()
        assert assessment.primary is None
        assert bare.get_most_restrictive_jurisdictions(assessment) == []


class TestVerdictShape:
    def test_inapplicable_regimes_are_reported_with_a_reason(self, engine):
        verdicts = {v.code: v for v in engine.evaluate(profile(deployment_regions=["DE"])).verdicts}
        assert verdicts["IN"].applicable is False
        assert verdicts["IN"].confidence == 0.0
        assert "nexus detected" in verdicts["IN"].reasons[0]

    def test_confidence_rises_with_amplifiers_and_is_capped(self, engine):
        plain = engine.evaluate(profile(data_residency_regions=["DE"]))
        loaded = engine.evaluate(
            profile(
                data_residency_regions=["DE"],
                uses_biometrics=True,
                affects_minors=True,
                uses_generative_ai=True,
            )
        )
        plain_eu = next(v for v in plain.verdicts if v.code == "EU")
        loaded_eu = next(v for v in loaded.verdicts if v.code == "EU")
        assert loaded_eu.confidence > plain_eu.confidence
        assert all(0.0 <= v.confidence <= 1.0 for v in loaded.verdicts)

    def test_strongest_nexus_sets_the_confidence_floor(self, engine):
        deployed = engine.evaluate(profile(deployment_regions=["DE"]))
        reachable = engine.evaluate(profile(service_accessible_regions=["CN"]))
        eu = next(v for v in deployed.verdicts if v.code == "EU")
        cn = next(v for v in reachable.verdicts if v.code == "CN")
        # Running inside a territory is stronger evidence than merely being reachable.
        assert eu.confidence > cn.confidence

    def test_reasons_are_ordered_by_strength(self, engine):
        p = profile(deployment_regions=["DE"], data_residency_regions=["FR"])
        eu = next(v for v in engine.evaluate(p).verdicts if v.code == "EU")
        assert eu.reasons[0].startswith("Deployed in")

    def test_matched_territories_are_collapsed(self, engine):
        p = profile(deployment_regions=["EU"], data_subject_regions=["DE"])
        eu = next(v for v in engine.evaluate(p).verdicts if v.code == "EU")
        assert eu.matched_territories == ("EU",)

    def test_data_categories_can_stand_in_for_boolean_flags(self, engine):
        p = profile(deployment_regions=["DE"], data_categories=frozenset({"biometric"}))
        assert "biometric_processing" in signals_for(engine, p, "EU")


class TestPurityAndDeterminism:
    def test_profile_is_immutable(self):
        p = profile(deployment_regions=["DE"])
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.use_case = "x"  # type: ignore[misc]

    def test_repeated_evaluation_is_identical(self, engine):
        p = profile(deployment_regions=["DE", "IN"], uses_generative_ai=True)
        assert engine.evaluate(p) == engine.evaluate(p)

    def test_evaluation_does_not_mutate_the_profile(self, engine):
        p = profile(deployment_regions=["DE"], use_case="credit_scoring")
        before = dataclasses.asdict(p)
        engine.evaluate(p)
        assert dataclasses.asdict(p) == before


# ---------------------------------------------------------------------------
# Configurability
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_rules_can_be_supplied_as_plain_config(self):
        engine = JurisdictionEngine.from_config(
            [
                {
                    "code": "br",
                    "name": "Brazil",
                    "territories": ["Brazil"],
                    "strictness": 65,
                    "triggers": ["deployment_nexus", "data_subject_nexus"],
                }
            ]
        )
        assessment = engine.evaluate(profile(deployment_regions=["BR"]))
        assert assessment.applicable_codes == ("BR",)
        assert assessment.verdicts[0].name == "Brazil"

    def test_unknown_trigger_in_config_is_rejected_loudly(self):
        with pytest.raises(ValueError, match="unknown triggers"):
            JurisdictionRule.from_config(
                {"code": "XX", "name": "X", "triggers": ["teleportation_nexus"]}
            )

    def test_unknown_trigger_at_evaluation_time_is_skipped_not_fatal(self):
        # Config written directly (not via from_config) must not break evaluation.
        rule = JurisdictionRule(
            code="XX",
            name="X",
            territories=frozenset({"IN"}),
            triggers=("deployment_nexus", "not_a_real_trigger"),
        )
        assessment = JurisdictionEngine([rule]).evaluate(profile(deployment_regions=["IN"]))
        assert assessment.applicable_codes == ("XX",)

    def test_consequential_use_cases_are_overridable_per_jurisdiction(self):
        rule = JurisdictionRule(
            code="XX",
            name="X",
            territories=frozenset({"IN"}),
            strictness=50,
            triggers=("consequential_decision_nexus",),
            consequential_use_cases=frozenset({"content_ranking"}),
        )
        engine = JurisdictionEngine([rule])
        p = profile(
            data_subject_regions=["IN"], use_case="content_ranking", makes_automated_decisions=True
        )
        assert engine.evaluate(p).applicable_codes == ("XX",)
        # A use case that is consequential by default is not, for this jurisdiction.
        other = profile(
            data_subject_regions=["IN"], use_case="credit_scoring", makes_automated_decisions=True
        )
        assert engine.evaluate(other).applicable_codes == ()

    def test_default_consequential_set_covers_the_expected_domains(self):
        assert {"employment_screening", "credit_scoring"} <= DEFAULT_CONSEQUENTIAL_USE_CASES

    def test_every_default_rule_names_registered_triggers(self):
        for rule in DEFAULT_RULES:
            unknown = [t for t in rule.triggers if t not in TRIGGER_REGISTRY]
            assert unknown == [], f"{rule.code} references {unknown}"

    def test_amplifiers_are_registered_as_amplifiers(self):
        for name in ("biometric_processing", "childrens_data", "generative_ai_service"):
            assert TRIGGER_REGISTRY[name].kind is TriggerKind.AMPLIFIER
        assert TRIGGER_REGISTRY["deployment_nexus"].kind is TriggerKind.NEXUS


# ---------------------------------------------------------------------------
# Boundary adapters (the only parts that touch ORM objects)
# ---------------------------------------------------------------------------


class TestAdapters:
    def test_profile_from_system_normalises_metadata(self, high_risk_system):
        high_risk_system.system_metadata.deployment_regions = ["Germany"]
        high_risk_system.system_metadata.data_subject_regions = ["california"]
        p = SystemProfile.from_system(high_risk_system)
        assert p.deployment_regions == frozenset({"DE"})
        assert p.data_subject_regions == frozenset({"US-CA"})
        assert p.use_case == "employment_screening"
        assert p.system_name == "Resume Screener"

    def test_profile_survives_a_system_without_metadata(self, high_risk_system):
        high_risk_system.system_metadata = None
        p = SystemProfile.from_system(high_risk_system)
        assert p.deployment_regions == frozenset()
        assert JurisdictionEngine().evaluate(p).applicable_codes == ("GLOBAL",)

    def test_rules_from_rows_use_stored_config(self, eu_jurisdiction):
        eu_jurisdiction.overlay_config = {
            "strictness": 42,
            "triggers": ["deployment_nexus"],
        }
        rule = rules_from_jurisdiction_rows([eu_jurisdiction])[0]
        assert rule.code == "EU"
        assert rule.strictness == 42
        assert rule.triggers == ("deployment_nexus",)

    def test_rules_from_rows_fall_back_to_built_in_defaults(self, eu_jurisdiction):
        eu_jurisdiction.overlay_config = {}
        rule = rules_from_jurisdiction_rows([eu_jurisdiction])[0]
        assert "consequential_decision_nexus" in rule.triggers
        assert rule.strictness == 100

    def test_load_engine_reads_active_jurisdictions(self, db, eu_jurisdiction, in_jurisdiction):
        from app.services.jurisdiction_engine import load_engine

        in_jurisdiction.is_active = False
        db.flush()
        engine = load_engine(db)
        assert [r.code for r in engine.rules] == ["EU"]

    def test_load_engine_falls_back_when_nothing_configured(self, db):
        from app.services.jurisdiction_engine import load_engine

        assert [r.code for r in load_engine(db).rules] == [r.code for r in DEFAULT_RULES]


class TestStoredConfigCompatibility:
    """Guards against stored configuration silently disabling a jurisdiction."""

    def test_legacy_dict_triggers_fall_back_to_defaults(self, eu_jurisdiction):
        # v1 stored triggers as {metadata_field: reason}. Those are not trigger names.
        eu_jurisdiction.overlay_config = {
            "strictness": 100,
            "triggers": {"uses_biometrics": "Biometric processing draws scrutiny"},
        }
        rule = rules_from_jurisdiction_rows([eu_jurisdiction])[0]
        assert "deployment_nexus" in rule.triggers
        assert JurisdictionEngine([rule]).evaluate(
            profile(deployment_regions=["DE"])
        ).applicable_codes == ("EU",)

    def test_partially_unknown_triggers_keep_the_known_ones(self, eu_jurisdiction):
        eu_jurisdiction.overlay_config = {
            "triggers": ["deployment_nexus", "nonsense_nexus"],
        }
        assert rules_from_jurisdiction_rows([eu_jurisdiction])[0].triggers == ("deployment_nexus",)

    def test_seeded_jurisdictions_produce_working_rules(self):
        """The shipped seed data must evaluate, not silently match nothing."""
        from types import SimpleNamespace

        from app.db.seed import JURISDICTIONS

        rows = [
            SimpleNamespace(
                code=j["code"],
                name=j["name"],
                regulation_name=j.get("regulation_name"),
                territories=j["territories"],
                overlay_config=j["overlay_config"],
            )
            for j in JURISDICTIONS
        ]
        engine = JurisdictionEngine(rules_from_jurisdiction_rows(rows))
        for rule in engine.rules:
            assert all(t in TRIGGER_REGISTRY for t in rule.triggers), rule.code

        # A generative service on the public internet reaches China.
        copilot = profile(
            deployment_regions=["EU"],
            data_subject_regions=["EU", "IN"],
            service_accessible_regions=["GLOBAL"],
            content_accessible_regions=["GLOBAL"],
            uses_generative_ai=True,
        )
        assessment = engine.evaluate(copilot)
        assert assessment.evaluation_order[:2] == ("EU", "CN")
        assert "IN" in assessment.applicable_codes

        # An India-only internal tool stays out of every other regime.
        forecaster = profile(
            deployment_regions=["IN"], data_residency_regions=["IN"], offered_in_regions=["IN"]
        )
        assert engine.evaluate(forecaster).applicable_codes == ("IN", "GLOBAL")
