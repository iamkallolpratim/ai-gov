# =============================================================================
# EU AI Act — shared helpers
# Regulation (EU) 2024/1689
#
# EU-specific vocabulary: scope, Annex III, the Art. 6(3) derogation. Generic
# helpers (metadata accessors, flags, special-category data, oversight, the
# finding shape) live in `aigov.common` and are re-exported below under their
# original names, so the EU packages and their tests did not have to change.
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

import data.aigov.common
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
# Re-exported from aigov.common
# -----------------------------------------------------------------------------

metadata := common.metadata

use_case := common.use_case

industry := common.industry

autonomy_level := common.autonomy_level

attributes := common.attributes

data_categories := common.data_categories

third_party_models := common.third_party_models

flag(name) if common.flag(name)

documented(name) if common.documented(name)

attribute(name) if common.attribute(name)

classified_high_risk if common.classified_high_risk

special_category_data := common.special_category_data

special_categories_present := common.special_categories_present

processes_special_category_data if common.processes_special_category_data

uses_biometrics if common.uses_biometrics

affects_minors if common.affects_minors

high_autonomy if common.high_autonomy

meaningful_human_oversight if common.meaningful_human_oversight

violation(rule_id, article, severity, explanation, remediation) := common.violation(rule_id, article, severity, explanation, remediation)

# -----------------------------------------------------------------------------
# EU risk posture
# -----------------------------------------------------------------------------

# Independently of the tier, the use case may be listed in Annex III.
annex_iii_listed if annex_iii_citation

# Treated as high-risk if any signal fires. Kept deliberately broad: it is far
# cheaper to document a system that turns out to be limited-risk than to miss one.
is_high_risk if classified_high_risk

is_high_risk if annex_iii_listed

is_high_risk if flag("is_safety_component")

# Art. 6(3) lets a provider rebut the Annex III presumption (the system performs a
# narrow procedural task, does not materially influence the outcome, and so on).
# The derogation only counts when the assessment is documented and registered.
derogation_claimed if attribute("art_6_3_derogation_documented")
