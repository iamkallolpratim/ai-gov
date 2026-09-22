# =============================================================================
# Shared vocabulary for every jurisdiction's policy packages
#
# Nothing here makes a decision. It normalises the input document, answers the
# questions every regime asks ("is oversight documented?", "is special category
# data processed?"), and defines the two finding shapes all packages emit, so
# PolicyService renders results uniformly whichever package produced them.
#
# Jurisdiction-specific vocabulary (the EU's Annex III, Colorado's consequential
# decisions, Korea's high-impact AI) belongs in that jurisdiction's own base.
#
# Input contract (produced by PolicyService.build_input):
#
#   {
#     "system":       {"id", "name", "status", "metadata_version", "extra"},
#     "metadata":     {...structured compliance metadata...},
#     "jurisdiction": "EU" | "CN" | "CA" | ...,
#     "risk_tier":    "prohibited" | "high" | "limited" | "minimal" | "unknown"
#   }
# =============================================================================
package aigov.common

import rego.v1

# -----------------------------------------------------------------------------
# Normalised metadata accessors
#
# Every accessor tolerates a missing key: inventory records are filled in
# progressively, and a half-complete record must still evaluate rather than error.
# -----------------------------------------------------------------------------

metadata := object.get(input, "metadata", {})

use_case := lower(object.get(metadata, "use_case", ""))

industry := lower(object.get(metadata, "industry", ""))

autonomy_level := lower(object.get(metadata, "autonomy_level", ""))

attributes := object.get(metadata, "attributes", {})

data_categories := {lower(c) | some c in object.get(metadata, "data_categories", [])}

third_party_models := object.get(metadata, "third_party_models", [])

# Region sets, upper-cased. Province- or state-level rules (Quebec Law 25, for
# example) check these directly rather than relying on the jurisdiction alone.
deployment_regions := {upper(r) | some r in object.get(metadata, "deployment_regions", [])}

data_subject_regions := {upper(r) | some r in object.get(metadata, "data_subject_regions", [])}

data_residency := {upper(r) | some r in object.get(metadata, "data_residency", [])}

offered_in_regions := {upper(r) | some r in object.get(metadata, "offered_in_regions", [])}

# Anywhere real people meet the system or its data lives.
reached_regions := ((deployment_regions | data_subject_regions) | offered_in_regions) | data_residency

# Boolean metadata flag, defaulting to false when absent.
flag(name) if object.get(metadata, name, false) == true

# A string field is "documented" when it is present and not blank.
documented(name) if {
	value := object.get(metadata, name, null)
	is_string(value)
	trim_space(value) != ""
}

# An attribute flag under metadata.attributes, defaulting to false.
attribute(name) if object.get(attributes, name, false) == true

# -----------------------------------------------------------------------------
# Risk posture
# -----------------------------------------------------------------------------

# The console's classifier already ran for this jurisdiction; trust its tier.
classified_high_risk if input.risk_tier in {"high", "prohibited"}

# -----------------------------------------------------------------------------
# Special category and sensitive data (GDPR Art. 9 shaped; most regimes align)
# -----------------------------------------------------------------------------

special_category_data := {
	"biometric",
	"genetic",
	"health",
	"racial_origin",
	"ethnic_origin",
	"political_opinions",
	"religious_beliefs",
	"trade_union_membership",
	"sex_life",
	"sexual_orientation",
	"criminal_convictions",
}

special_categories_present := data_categories & special_category_data

processes_special_category_data if count(special_categories_present) > 0

# Biometrics can be declared either as a flag or as a data category.
uses_biometrics if flag("uses_biometrics")

uses_biometrics if "biometric" in data_categories

affects_minors if flag("affects_minors")

affects_minors if "children" in data_categories

# -----------------------------------------------------------------------------
# Oversight and autonomy
# -----------------------------------------------------------------------------

high_autonomy if autonomy_level == "fully_autonomous"

meaningful_human_oversight if {
	flag("human_oversight_documented")
	not high_autonomy
}

# A fully autonomous system can still have meaningful oversight, but only with a
# documented stop/override capability; a reviewer who cannot intervene is not one.
meaningful_human_oversight if {
	flag("human_oversight_documented")
	high_autonomy
	attribute("human_override_capability")
}

# -----------------------------------------------------------------------------
# Findings
# -----------------------------------------------------------------------------

# A finding against law that is in force. Severity decides whether PolicyService
# reports it as a failure (critical/high/medium) or a warning (low/info).
violation(rule_id, article, severity, explanation, remediation) := {
	"rule_id": rule_id,
	"article": article,
	"severity": severity,
	"msg": explanation,
	"remediation": remediation,
}

# A finding against an obligation that is not binding yet: a bill still in
# passage, or an enacted act before its effective date. Always `low`, so it
# surfaces as a warning and never blocks compliance. `effective` is an RFC 3339
# date, or "pending" for a bill with no date.
readiness_violation(rule_id, article, explanation, remediation, effective, source) := {
	"rule_id": rule_id,
	"article": article,
	"severity": "low",
	"msg": explanation,
	"remediation": remediation,
	"status": "not_in_force",
	"effective_date": effective,
	"source": source,
}

# True once an RFC 3339 effective date has passed. Tests pin the clock with
# `with time.now_ns as ...`.
enforced(effective) if time.now_ns() >= time.parse_rfc3339_ns(effective)

# An obligation with a known effective date: a readiness finding before it, a real
# finding at `severity` from it. Encoding the date here means a rule switches over
# on its own, with no code change on the day the law takes effect.
obligation(rule_id, article, severity, explanation, remediation, effective, source) := finding if {
	enforced(effective)
	finding := object.union(
		violation(rule_id, article, severity, explanation, remediation),
		{"status": "in_force", "effective_date": effective, "source": source},
	)
}

obligation(rule_id, article, severity, explanation, remediation, effective, source) := finding if {
	not enforced(effective)
	finding := readiness_violation(rule_id, article, explanation, remediation, effective, source)
}
