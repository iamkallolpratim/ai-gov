package aigov.eu.prohibited_test

import data.aigov.eu.prohibited
import rego.v1

base_input(use_case, attributes) := {
	"jurisdiction": "EU",
	"risk_tier": "high",
	"metadata": {
		"use_case": use_case,
		"industry": "retail",
		"data_categories": [],
		"attributes": attributes,
	},
}

test_ordinary_use_case_allowed if {
	prohibited.allow with input as base_input("customer_support", {})
}

test_social_scoring_denied if {
	result := prohibited.result with input as base_input("social_scoring", {})
	result.decision == "deny"
	result.severity == "critical"
	"eu.prohibited.art_5_1_c.social_scoring" in result.rule_ids
}

test_untargeted_face_scraping_denied if {
	result := prohibited.result with input as base_input("untargeted_face_scraping", {})
	"eu.prohibited.art_5_1_e.face_scraping" in result.rule_ids
}

test_workplace_emotion_recognition_denied if {
	result := prohibited.result with input as base_input("emotion_recognition_workplace", {})
	"eu.prohibited.art_5_1_f.emotion_recognition" in result.rule_ids
}

test_emotion_recognition_with_safety_exemption_allowed if {
	prohibited.allow with input as base_input(
		"emotion_recognition_workplace",
		{"emotion_recognition_medical_or_safety_exemption": true},
	)
}

test_emotion_recognition_outside_work_or_education_allowed if {
	prohibited.allow with input as base_input("emotion_recognition", {})
}

test_biometric_categorisation_inferring_protected_traits_denied if {
	result := prohibited.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {
			"use_case": "biometric_categorisation",
			"industry": "retail",
			"data_categories": ["biometric", "political_opinions"],
			"attributes": {},
		},
	}
	"eu.prohibited.art_5_1_g.biometric_categorisation" in result.rule_ids
}

test_law_enforcement_realtime_biometric_id_denied_without_authorisation if {
	result := prohibited.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {
			"use_case": "biometric_identification",
			"industry": "law_enforcement",
			"data_categories": ["biometric"],
			"attributes": {"realtime_identification": true, "publicly_accessible_space": true},
		},
	}
	"eu.prohibited.art_5_1_h.realtime_biometric_id" in result.rule_ids
}

test_law_enforcement_realtime_biometric_id_allowed_with_authorisation if {
	prohibited.allow with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {
			"use_case": "biometric_identification",
			"industry": "law_enforcement",
			"data_categories": ["biometric"],
			"attributes": {
				"realtime_identification": true,
				"publicly_accessible_space": true,
				"judicial_authorisation": true,
			},
		},
	}
}

test_commercial_realtime_biometrics_flagged_but_not_a_ban if {
	result := prohibited.result with input as {
		"jurisdiction": "EU",
		"risk_tier": "high",
		"metadata": {
			"use_case": "biometric_identification",
			"industry": "retail",
			"data_categories": ["biometric"],
			"attributes": {"realtime_identification": true, "publicly_accessible_space": true},
		},
	}
	"eu.prohibited.art_5_1_h.biometric_legal_basis" in result.rule_ids
	some v in result.violations
	v.rule_id == "eu.prohibited.art_5_1_h.biometric_legal_basis"
	v.severity == "high"
}

test_non_eu_system_untouched if {
	result := prohibited.result with input as {
		"jurisdiction": "CN",
		"risk_tier": "high",
		"metadata": {"use_case": "social_scoring", "attributes": {}},
	}
	result.in_scope == false
	result.allow == true
}
