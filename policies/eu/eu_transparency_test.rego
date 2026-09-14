package aigov.eu.transparency_test

import data.aigov.eu.transparency
import rego.v1

generative_system(attributes) := {
	"jurisdiction": "EU",
	"risk_tier": "limited",
	"metadata": {
		"use_case": "customer_support",
		"industry": "saas",
		"uses_generative_ai": true,
		"data_categories": [],
		"third_party_models": [],
		"attributes": attributes,
	},
}

test_undisclosed_generative_assistant_denied if {
	result := transparency.result with input as generative_system({})
	result.decision == "deny"
	"eu.transparency.art_50_1.interaction_disclosure" in result.rule_ids
	"eu.transparency.art_50_2.synthetic_content_marking" in result.rule_ids
}

test_fully_disclosed_generative_assistant_allowed if {
	transparency.allow with input as generative_system({
		"ai_interaction_disclosed": true,
		"synthetic_content_marked": true,
		"accessible_disclosures": true,
	})
}

test_non_interactive_system_has_no_disclosure_duty if {
	transparency.allow with input as {
		"jurisdiction": "EU",
		"risk_tier": "minimal",
		"metadata": {
			"use_case": "demand_forecasting",
			"data_categories": [],
			"third_party_models": [],
			"attributes": {},
		},
	}
}

test_deepfake_requires_disclosure if {
	result := transparency.result with input as generative_system({
		"ai_interaction_disclosed": true,
		"synthetic_content_marked": true,
		"generates_deepfakes": true,
	})
	"eu.transparency.art_50_4.deepfake_disclosure" in result.rule_ids
}

test_biometric_processing_requires_notice if {
	result := transparency.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {
			"use_case": "emotion_recognition",
			"data_categories": ["biometric"],
			"third_party_models": [],
			"attributes": {},
		},
	}
	"eu.transparency.art_50_3.biometric_notice" in result.rule_ids
}

test_third_party_models_require_gpai_documentation if {
	result := transparency.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "limited",
		"metadata": {
			"use_case": "customer_support",
			"uses_generative_ai": true,
			"data_categories": [],
			"third_party_models": ["claude-sonnet-5"],
			"attributes": {"ai_interaction_disclosed": true, "synthetic_content_marked": true},
		},
	}
	"eu.transparency.art_53.gpai_documentation" in result.rule_ids
}

test_accessibility_duty_follows_a_notice_duty if {
	result := transparency.result with input as generative_system({"synthetic_content_marked": true})
	"eu.transparency.art_50_5.accessible_format" in result.rule_ids
}

test_severity_is_lower_than_high_risk_findings if {
	result := transparency.result with input as generative_system({})
	result.severity in {"high", "medium", "low"}
}
