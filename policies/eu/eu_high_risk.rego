# =============================================================================
# EU AI Act — obligations for high-risk AI systems
# Regulation (EU) 2024/1689, Chapter III Section 2 (Art. 9–15) and Art. 43, 49, 72, 73
#
# Scope: fires only for systems the console routed to the EU and that are either
# classified high-risk, listed in Annex III, or acting as a product safety
# component. Everything else is allowed by this package without comment — a
# minimal-risk internal tool must not be told to run a conformity assessment.
#
# Result document:
#   {
#     "allow":       bool,          # false when any violation was raised
#     "decision":    "allow"|"deny",
#     "in_scope":    bool,          # did the package evaluate this system at all
#     "rule_ids":    [...],         # every rule that fired
#     "severity":    "critical"|"high"|"medium"|"low",   # worst severity present
#     "violations":  [ {rule_id, article, severity, msg, remediation}, ... ]
#   }
# =============================================================================
package aigov.eu.high_risk

import data.aigov.eu.base
import rego.v1

# -----------------------------------------------------------------------------
# Scope
# -----------------------------------------------------------------------------

default in_scope := false

in_scope if {
	base.in_eu_scope
	base.is_high_risk
	not base.derogation_claimed
}

# -----------------------------------------------------------------------------
# Decision
# -----------------------------------------------------------------------------

default allow := false

# Out of scope is an unconditional pass: this package has nothing to say.
allow if not in_scope

allow if {
	in_scope
	count(violations) == 0
}

decision := "allow" if allow

decision := "deny" if not allow

# Ranked so the worst severity present can be reported as the headline.
severity_rank := {"critical": 4, "high": 3, "medium": 2, "low": 1}

severity := s if {
	count(violations) > 0
	ranks := [severity_rank[v.severity] | some v in violations]
	top := max(ranks)
	some name, rank in severity_rank
	rank == top
	s := name
}

severity := "none" if count(violations) == 0

rule_ids := sort([v.rule_id | some v in violations])

result := {
	"allow": allow,
	"decision": decision,
	"in_scope": in_scope,
	"rule_ids": rule_ids,
	"severity": severity,
	"violations": violations,
}

# -----------------------------------------------------------------------------
# Art. 9 — Risk management system
#
# A risk management system must be established, implemented, documented and
# maintained across the whole lifecycle. It is the backbone obligation: without
# it none of the others can be evidenced.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.attribute("risk_management_system")
	v := base.violation(
		"eu.high_risk.art_9.risk_management_system",
		"Art. 9",
		"critical",
		sprintf(
			"No risk management system is recorded for this high-risk system (%v). Art. 9 requires a continuous, documented process that identifies and mitigates foreseeable risks to health, safety and fundamental rights across the entire lifecycle.",
			[scope_reason],
		),
		"Establish and document a lifecycle risk management system covering risk identification, evaluation, mitigation and residual-risk acceptance, then set metadata attribute 'risk_management_system' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 10 — Data and data governance
#
# Training, validation and testing sets must be relevant, representative and, as
# far as possible, free of errors. Special category data raises the bar further:
# Art. 10(5) only permits processing it for bias detection under strict safeguards.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.flag("training_data_documented")
	v := base.violation(
		"eu.high_risk.art_10.data_governance",
		"Art. 10",
		"high",
		"Training, validation and testing data sets are not documented. Art. 10 requires documented data governance covering provenance, collection purpose, representativeness and examination for bias.",
		"Document each data set's provenance, collection methodology, coverage of the intended population, and the bias examination performed on it, then set 'training_data_documented' to true.",
	)
}

violations contains v if {
	in_scope
	base.processes_special_category_data
	not base.attribute("special_category_safeguards")
	v := base.violation(
		"eu.high_risk.art_10_5.special_category_safeguards",
		"Art. 10(5)",
		"critical",
		sprintf(
			"Special category data is processed (%v) without recorded safeguards. Art. 10(5) permits this only where strictly necessary for bias detection and correction, subject to pseudonymisation, access limits and deletion after use.",
			[concat(", ", sort(base.special_categories_present))],
		),
		"Record the strict-necessity justification, apply pseudonymisation and access controls, define a deletion schedule, and set attribute 'special_category_safeguards' to true — or remove the special category data from the pipeline.",
	)
}

# -----------------------------------------------------------------------------
# Art. 11 + Annex IV — Technical documentation
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.documented("technical_documentation_url")
	v := base.violation(
		"eu.high_risk.art_11.technical_documentation",
		"Art. 11 / Annex IV",
		"critical",
		"No technical documentation is recorded. Art. 11 requires Annex IV documentation to exist before the system is placed on the market and to be kept up to date thereafter.",
		"Produce Annex IV technical documentation (system description, development process, monitoring, performance metrics, risk management) and record its location in 'technical_documentation_url'.",
	)
}

# -----------------------------------------------------------------------------
# Art. 12 — Record keeping (logging)
#
# High-risk systems must log automatically over their lifetime. Art. 19 then
# requires providers to retain those logs for at least six months.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.attribute("automatic_logging_enabled")
	v := base.violation(
		"eu.high_risk.art_12.record_keeping",
		"Art. 12",
		"high",
		"Automatic event logging is not enabled. Art. 12 requires high-risk systems to record events over their lifetime so that operation is traceable and post-market monitoring is possible.",
		"Enable automatic logging of inputs, outputs, reference data and human interventions, retain the logs for at least six months (Art. 19), and set attribute 'automatic_logging_enabled' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 13 — Transparency towards deployers
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.attribute("instructions_for_use")
	v := base.violation(
		"eu.high_risk.art_13.instructions_for_use",
		"Art. 13",
		"medium",
		"No instructions for use are recorded. Art. 13 requires high-risk systems to be accompanied by instructions that let deployers interpret the output and use the system appropriately.",
		"Publish instructions for use covering intended purpose, accuracy and known limitations, required human oversight measures, and expected lifetime, then set attribute 'instructions_for_use' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 14 — Human oversight
#
# Two distinct failures: no oversight at all, and oversight that is nominal
# because the system runs fully autonomously with no documented way to intervene.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.flag("human_oversight_documented")
	v := base.violation(
		"eu.high_risk.art_14.human_oversight_missing",
		"Art. 14",
		"critical",
		"No human oversight measures are documented. Art. 14 requires high-risk systems to be designed so that natural persons can effectively oversee them while in use.",
		"Assign named oversight roles, document how reviewers interpret output and when they must intervene, and set 'human_oversight_documented' to true.",
	)
}

violations contains v if {
	in_scope
	base.flag("human_oversight_documented")
	base.high_autonomy
	not base.attribute("human_override_capability")
	v := base.violation(
		"eu.high_risk.art_14.oversight_not_effective",
		"Art. 14(4)",
		"critical",
		"The system operates fully autonomously and no override capability is recorded, so the documented oversight cannot be exercised. Art. 14(4)(d)-(e) require the overseer to be able to disregard the output and to stop the system.",
		"Implement a stop button or equivalent interrupt and a documented route for the overseer to override a decision, then set attribute 'human_override_capability' to true.",
	)
}

# Automated decisions about people, with nobody able to review an individual
# outcome, is the combination that produces real-world harm fastest.
violations contains v if {
	in_scope
	base.flag("makes_automated_decisions")
	not base.attribute("human_review_of_individual_decisions")
	v := base.violation(
		"eu.high_risk.art_14.no_individual_review",
		"Art. 14",
		"high",
		"The system makes automated decisions about individuals with no route for a human to review a single decision. Effective oversight under Art. 14 has to reach the individual outcome, not only aggregate performance.",
		"Provide a documented appeal or review path where an affected person's decision is re-examined by a competent human, then set attribute 'human_review_of_individual_decisions' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 15 — Accuracy, robustness and cybersecurity
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.attribute("accuracy_metrics_declared")
	v := base.violation(
		"eu.high_risk.art_15.accuracy_metrics",
		"Art. 15",
		"high",
		"No accuracy metrics are declared. Art. 15 requires high-risk systems to achieve an appropriate level of accuracy and to declare the metrics and levels in the instructions for use.",
		"Measure accuracy against a representative held-out set, declare the metric and level reached (including per-subgroup performance), and set attribute 'accuracy_metrics_declared' to true.",
	)
}

violations contains v if {
	in_scope
	not base.attribute("adversarial_robustness_tested")
	base.uses_biometrics
	v := base.violation(
		"eu.high_risk.art_15.robustness_testing",
		"Art. 15(5)",
		"high",
		"A biometric system has no adversarial robustness testing on record. Art. 15(5) requires resilience against attempts to alter use or performance, which for biometrics includes presentation and spoofing attacks.",
		"Run presentation-attack and adversarial robustness testing, record the results, and set attribute 'adversarial_robustness_tested' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 43 + 47 + 49 — Conformity assessment, declaration and registration
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.flag("conformity_assessment_done")
	v := base.violation(
		"eu.high_risk.art_43.conformity_assessment",
		"Art. 43",
		"critical",
		"No conformity assessment has been completed. Art. 43 requires the applicable assessment procedure to be carried out before a high-risk system is placed on the market or put into service.",
		"Complete the applicable conformity assessment procedure (Annex VI self-assessment, or Annex VII with a notified body where required), draw up the EU declaration of conformity, and set 'conformity_assessment_done' to true.",
	)
}

# Annex III systems must additionally be registered in the EU database.
violations contains v if {
	in_scope
	base.annex_iii_listed
	not base.attribute("eu_database_registered")
	v := base.violation(
		"eu.high_risk.art_49.eu_database_registration",
		"Art. 49",
		"high",
		sprintf(
			"This system falls under %v but is not registered in the EU database. Art. 49 requires providers to register Annex III high-risk systems before placing them on the market.",
			[base.annex_iii_citation],
		),
		"Register the system and its provider in the EU database maintained under Art. 71, then set attribute 'eu_database_registered' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 72 + 73 — Post-market monitoring and serious incident reporting
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	not base.attribute("post_market_monitoring_plan")
	v := base.violation(
		"eu.high_risk.art_72.post_market_monitoring",
		"Art. 72",
		"medium",
		"No post-market monitoring plan is recorded. Art. 72 requires providers to actively collect and review performance data throughout the system's lifetime.",
		"Define a post-market monitoring plan covering the data collected, review cadence and escalation path, then set attribute 'post_market_monitoring_plan' to true.",
	)
}

violations contains v if {
	in_scope
	not base.flag("incident_response_plan")
	v := base.violation(
		"eu.high_risk.art_73.incident_reporting",
		"Art. 73",
		"high",
		"No serious incident response plan is recorded. Art. 73 requires providers to report serious incidents to the market surveillance authority, in most cases within 15 days of becoming aware of them.",
		"Define an incident response and reporting procedure that meets the Art. 73 deadlines (immediately and no later than 15 days; 2 days for widespread infringement; 10 days on death), then set 'incident_response_plan' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 25 + 27 — Value chain and deployer duties
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	count(base.third_party_models) > 0
	not base.attribute("upstream_provider_agreement")
	v := base.violation(
		"eu.high_risk.art_25.value_chain_agreement",
		"Art. 25",
		"medium",
		sprintf(
			"This high-risk system builds on third-party models (%v) with no upstream provider agreement on record. Art. 25 requires the information and assistance needed for compliance to be secured in writing along the value chain.",
			[concat(", ", base.third_party_models)],
		),
		"Put a written agreement in place with each model provider covering documentation, technical access and assistance obligations, then set attribute 'upstream_provider_agreement' to true.",
	)
}

# Public bodies and providers of essential services owe a fundamental rights
# impact assessment before first use (Art. 27).
violations contains v if {
	in_scope
	fria_required
	not base.attribute("fundamental_rights_impact_assessment")
	v := base.violation(
		"eu.high_risk.art_27.fria",
		"Art. 27",
		"high",
		"No fundamental rights impact assessment is recorded, although this system's deployment context requires one. Art. 27 obliges public bodies, and providers of essential private services such as credit and insurance, to complete a FRIA before first use.",
		"Complete a fundamental rights impact assessment covering affected groups, specific risks of harm, human oversight measures and the governance arrangements, then set attribute 'fundamental_rights_impact_assessment' to true.",
	)
}

fria_required if base.use_case in {
	"credit_scoring",
	"insurance_underwriting",
	"benefits_eligibility",
	"essential_services",
	"emergency_triage",
	"law_enforcement",
	"migration_asylum",
	"border_control",
	"judicial_decision_support",
}

fria_required if base.industry in {"public_sector", "government", "law_enforcement"}

# -----------------------------------------------------------------------------
# Explanation helper
# -----------------------------------------------------------------------------

# Why this system was treated as high-risk, cited in the Art. 9 message.
scope_reason := base.annex_iii_citation if base.annex_iii_listed

scope_reason := "classified high-risk by the governance console" if {
	not base.annex_iii_listed
	base.classified_high_risk
}

scope_reason := "acts as a safety component of a product" if {
	not base.annex_iii_listed
	not base.classified_high_risk
	base.flag("is_safety_component")
}
