# =============================================================================
# EU AI Act — shared helpers
# Regulation (EU) 2024/1689
#
# Vocabulary used by every EU package. Nothing here makes a decision; it only
# normalises the input document and answers questions the individual policy
# packages ask ("is this an Annex III use case?", "is oversight documented?").
#
# Input contract (produced by PolicyService.build_input):
#
#   {
#     "system":      {"id", "name", "status", "metadata_version", "extra"},
#     "metadata":    {...structured compliance metadata...},
#     "jurisdiction": "EU",
#     "risk_tier":   "prohibited" | "high" | "limited" | "minimal" | "unknown"
#   }
# =============================================================================
package aigov.eu.base

import rego.v1

# -----------------------------------------------------------------------------
# Scope
# -----------------------------------------------------------------------------

# Every EU package is a no-op unless the console routed an EU evaluation to it.
in_eu_scope if input.jurisdiction == "EU"

# -----------------------------------------------------------------------------
# Annex III — high-risk use cases
#
# Grouped by Annex III point so explanations can cite the right one. These are
# the areas the Act treats as high-risk when the system is used for the listed
# purpose; the console's own use_case taxonomy maps onto them.
# -----------------------------------------------------------------------------

annex_iii_use_cases := {
	# 1. Biometrics
	"biometric_identification": "Annex III(1) — remote biometric identification",
	"biometric_categorisation": "Annex III(1) — biometric categorisation of natural persons",
	"emotion_recognition": "Annex III(1) — emotion recognition",
	# 2. Critical infrastructure
	"critical_infrastructure": "Annex III(2) — safety components of critical infrastructure",
	# 3. Education and vocational training
	"education_assessment": "Annex III(3) — determining access to, or evaluating learning outcomes in, education",
	"exam_proctoring": "Annex III(3) — monitoring prohibited behaviour during examinations",
	# 4. Employment and worker management
	"employment_screening": "Annex III(4) — recruitment and selection of natural persons",
	"worker_management": "Annex III(4) — decisions on promotion, termination or task allocation",
	"performance_evaluation": "Annex III(4) — monitoring and evaluating worker performance",
	# 5. Access to essential private and public services
	"credit_scoring": "Annex III(5) — evaluating creditworthiness or establishing credit scores",
	"benefits_eligibility": "Annex III(5) — eligibility for essential public assistance benefits",
	"insurance_underwriting": "Annex III(5) — risk assessment and pricing for life and health insurance",
	"emergency_triage": "Annex III(5) — dispatch and triage of emergency first-response services",
	"essential_services": "Annex III(5) — access to essential private or public services",
	# 6. Law enforcement
	"law_enforcement": "Annex III(6) — use by law enforcement authorities",
	"crime_risk_assessment": "Annex III(6) — assessing the risk of a person offending or re-offending",
	"evidence_reliability": "Annex III(6) — evaluating the reliability of evidence",
	# 7. Migration, asylum and border control
	"migration_asylum": "Annex III(7) — examination of asylum, visa and residence applications",
	"border_control": "Annex III(7) — border control management",
	# 8. Administration of justice and democratic processes
	"judicial_decision_support": "Annex III(8) — assisting judicial authorities in interpreting facts or law",
	"election_influence": "Annex III(8) — influencing the outcome of an election or voting behaviour",
}

# The Annex III citation for this system, when its use case is listed.
annex_iii_citation := annex_iii_use_cases[use_case]

# -----------------------------------------------------------------------------
# Normalised metadata accessors
#
# Every accessor tolerates a missing key, because inventory records are filled in
# progressively and a half-complete record must still evaluate rather than error.
# -----------------------------------------------------------------------------

metadata := object.get(input, "metadata", {})

use_case := lower(object.get(metadata, "use_case", ""))

industry := lower(object.get(metadata, "industry", ""))

autonomy_level := lower(object.get(metadata, "autonomy_level", ""))

attributes := object.get(metadata, "attributes", {})

data_categories := {lower(c) | some c in object.get(metadata, "data_categories", [])}

third_party_models := object.get(metadata, "third_party_models", [])

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

# The console's own classifier already ran; trust its tier.
classified_high_risk if input.risk_tier in {"high", "prohibited"}

# Independently of the tier, the use case may be listed in Annex III.
annex_iii_listed if annex_iii_citation

# Treated as high-risk if either signal fires. Kept deliberately broad: it is far
# cheaper to document a system that turns out to be limited-risk than to miss one.
is_high_risk if classified_high_risk

is_high_risk if annex_iii_listed

is_high_risk if flag("is_safety_component")

# Art. 6(3) lets a provider rebut the Annex III presumption (the system performs a
# narrow procedural task, does not materially influence the outcome, and so on).
# The derogation only counts when the assessment is documented and registered.
derogation_claimed if attribute("art_6_3_derogation_documented")

# -----------------------------------------------------------------------------
# Special category and sensitive data (GDPR Art. 9 shaped)
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

# A fully autonomous system can still satisfy Art. 14, but only with a documented
# stop/override capability — a named reviewer who cannot intervene is not oversight.
meaningful_human_oversight if {
	flag("human_oversight_documented")
	high_autonomy
	attribute("human_override_capability")
}

# -----------------------------------------------------------------------------
# Decision helpers
#
# Every rule in every EU package emits this shape, so PolicyService can render
# results uniformly without knowing which package produced them.
# -----------------------------------------------------------------------------

violation(rule_id, article, severity, explanation, remediation) := {
	"rule_id": rule_id,
	"article": article,
	"severity": severity,
	"msg": explanation,
	"remediation": remediation,
}
