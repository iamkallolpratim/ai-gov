# Rego unit tests for the shared library. Run with: opa test policies/
package aigov.common_test

import data.aigov.common
import rego.v1

test_missing_metadata_does_not_error if {
	common.use_case == "" with input as {}
	count(common.data_categories) == 0 with input as {}
	not common.flag("human_oversight_documented") with input as {}
}

test_flag_attribute_and_documented if {
	sample := {"metadata": {
		"human_oversight_documented": true,
		"technical_documentation_url": "https://docs.example.com",
		"attributes": {"risk_management_system": true},
	}}
	common.flag("human_oversight_documented") with input as sample
	common.attribute("risk_management_system") with input as sample
	common.documented("technical_documentation_url") with input as sample
}

test_blank_string_is_not_documented if {
	not common.documented("technical_documentation_url") with input as {"metadata": {"technical_documentation_url": "   "}}
}

test_biometrics_from_flag_or_category if {
	common.uses_biometrics with input as {"metadata": {"uses_biometrics": true}}
	common.uses_biometrics with input as {"metadata": {"data_categories": ["Biometric"]}}
}

test_reached_regions_are_upper_cased_and_merged if {
	regions := common.reached_regions with input as {"metadata": {
		"deployment_regions": ["us-ny"],
		"data_subject_regions": ["CA-QC"],
		"offered_in_regions": ["kr"],
	}}
	regions == {"US-NY", "CA-QC", "KR"}
}

test_fully_autonomous_needs_override_for_oversight if {
	not common.meaningful_human_oversight with input as {"metadata": {
		"human_oversight_documented": true,
		"autonomy_level": "fully_autonomous",
	}}
	common.meaningful_human_oversight with input as {"metadata": {
		"human_oversight_documented": true,
		"autonomy_level": "fully_autonomous",
		"attributes": {"human_override_capability": true},
	}}
}

test_readiness_violation_is_low_and_marked if {
	finding := common.readiness_violation("x.rule", "Art. 1", "msg", "fix", "pending", "Bill 1")
	finding.severity == "low"
	finding.status == "not_in_force"
	finding.effective_date == "pending"
	finding.source == "Bill 1"
}

test_obligation_is_readiness_before_its_effective_date if {
	before := time.parse_rfc3339_ns("2026-06-29T00:00:00Z")
	finding := common.obligation("co.rule", "§ 6-1-1703", "critical", "msg", "fix", "2026-06-30T00:00:00Z", "SB 24-205") with time.now_ns as before
	finding.severity == "low"
	finding.status == "not_in_force"
}

test_obligation_is_enforced_from_its_effective_date if {
	after := time.parse_rfc3339_ns("2026-06-30T00:00:00Z")
	finding := common.obligation("co.rule", "§ 6-1-1703", "critical", "msg", "fix", "2026-06-30T00:00:00Z", "SB 24-205") with time.now_ns as after
	finding.severity == "critical"
	finding.status == "in_force"
	finding.rule_id == "co.rule"
}
