# Rego unit tests for the EU high-risk package. Run with: opa test policies/
package aigov.eu.high_risk_test

import data.aigov.eu.high_risk
import rego.v1

# A fully compliant high-risk employment system: every obligation satisfied.
compliant_high_risk := {
	"jurisdiction": "EU",
	"risk_tier": "high",
	"system": {"id": "1", "name": "Compliant Screener"},
	"metadata": {
		"use_case": "employment_screening",
		"industry": "hr_tech",
		"autonomy_level": "human_in_the_loop",
		"data_categories": ["personal_data"],
		"third_party_models": [],
		"makes_automated_decisions": true,
		"human_oversight_documented": true,
		"conformity_assessment_done": true,
		"training_data_documented": true,
		"incident_response_plan": true,
		"technical_documentation_url": "https://docs.example.com/annex-iv",
		"attributes": {
			"risk_management_system": true,
			"automatic_logging_enabled": true,
			"instructions_for_use": true,
			"accuracy_metrics_declared": true,
			"eu_database_registered": true,
			"post_market_monitoring_plan": true,
			"human_review_of_individual_decisions": true,
		},
	},
}

test_compliant_high_risk_system_allowed if {
	high_risk.allow with input as compliant_high_risk
}

test_undocumented_employment_system_denied if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(compliant_high_risk.metadata, {
			"human_oversight_documented": false,
			"conformity_assessment_done": false,
			"training_data_documented": false,
		})},
	)
	result.decision == "deny"
	result.severity == "critical"
	"eu.high_risk.art_14.human_oversight_missing" in result.rule_ids
	"eu.high_risk.art_43.conformity_assessment" in result.rule_ids
	"eu.high_risk.art_10.data_governance" in result.rule_ids
}

test_minimal_risk_system_out_of_scope if {
	result := high_risk.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "minimal",
		"metadata": {"use_case": "demand_forecasting", "attributes": {}},
	}
	result.in_scope == false
	result.allow == true
	count(result.violations) == 0
}

test_annex_iii_use_case_is_in_scope_even_when_tier_is_low if {
	# The classifier may be wrong or stale; Annex III membership alone pulls the
	# system into scope.
	result := high_risk.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "minimal",
		"metadata": {"use_case": "credit_scoring", "attributes": {}},
	}
	result.in_scope == true
	result.decision == "deny"
}

test_non_eu_system_untouched if {
	result := high_risk.result with input as {
		"jurisdiction": "IN",
		"risk_tier": "high",
		"metadata": {"use_case": "employment_screening", "attributes": {}},
	}
	result.in_scope == false
	result.allow == true
}

test_fully_autonomous_without_override_fails_oversight if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(compliant_high_risk.metadata, {"autonomy_level": "fully_autonomous"})},
	)
	"eu.high_risk.art_14.oversight_not_effective" in result.rule_ids
}

test_fully_autonomous_with_override_passes_oversight if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(compliant_high_risk.metadata, {
			"autonomy_level": "fully_autonomous",
			"attributes": object.union(
				compliant_high_risk.metadata.attributes,
				{"human_override_capability": true},
			),
		})},
	)
	not "eu.high_risk.art_14.oversight_not_effective" in result.rule_ids
	result.allow
}

test_special_category_data_requires_safeguards if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(
			compliant_high_risk.metadata,
			{"data_categories": ["personal_data", "health"]},
		)},
	)
	"eu.high_risk.art_10_5.special_category_safeguards" in result.rule_ids
	result.severity == "critical"
}

test_biometric_system_requires_robustness_testing if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(compliant_high_risk.metadata, {
			"use_case": "biometric_identification",
			"uses_biometrics": true,
		})},
	)
	"eu.high_risk.art_15.robustness_testing" in result.rule_ids
}

test_credit_scoring_requires_fria if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(compliant_high_risk.metadata, {"use_case": "credit_scoring"})},
	)
	"eu.high_risk.art_27.fria" in result.rule_ids
}

test_third_party_models_require_value_chain_agreement if {
	result := high_risk.result with input as object.union(
		compliant_high_risk,
		{"metadata": object.union(
			compliant_high_risk.metadata,
			{"third_party_models": ["claude-opus-5"]},
		)},
	)
	"eu.high_risk.art_25.value_chain_agreement" in result.rule_ids
}

test_documented_derogation_removes_system_from_scope if {
	result := high_risk.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {
			"use_case": "employment_screening",
			"attributes": {"art_6_3_derogation_documented": true},
		},
	}
	result.in_scope == false
	result.allow == true
}

test_safety_component_is_in_scope_without_annex_iii_use_case if {
	result := high_risk.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "minimal",
		"metadata": {
			"use_case": "predictive_maintenance",
			"is_safety_component": true,
			"attributes": {},
		},
	}
	result.in_scope == true
	"eu.high_risk.art_9.risk_management_system" in result.rule_ids
}

test_every_violation_carries_the_full_decision_shape if {
	result := high_risk.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {"use_case": "employment_screening", "attributes": {}},
	}
	every v in result.violations {
		is_string(v.rule_id)
		is_string(v.article)
		v.severity in {"critical", "high", "medium", "low"}
		count(v.msg) > 40
		count(v.remediation) > 40
	}
}
