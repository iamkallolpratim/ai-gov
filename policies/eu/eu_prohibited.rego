# =============================================================================
# EU AI Act — prohibited AI practices
# Regulation (EU) 2024/1689, Article 5 (applicable since 2 February 2025)
#
# These are bans, not obligations: no amount of documentation cures them. Every
# finding here is "critical" and the remediation is always to stop or re-scope
# the practice, never to file more paperwork.
#
# Art. 5 carries narrow exemptions (law-enforcement use of real-time remote
# biometric identification under judicial authorisation, medical or safety uses of
# emotion recognition). Those are modelled as documented, auditable attributes
# rather than being assumed.
# =============================================================================
package aigov.eu.prohibited

import data.aigov.eu.base
import rego.v1

default in_scope := false

in_scope if base.in_eu_scope

default allow := false

allow if not in_scope

allow if {
	in_scope
	count(violations) == 0
}

decision := "allow" if allow

decision := "deny" if not allow

severity := "critical" if count(violations) > 0

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
# Art. 5(1)(a)-(b) — Manipulation and exploitation of vulnerability
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.use_case in {"subliminal_manipulation", "behavioural_manipulation"}
	v := base.violation(
		"eu.prohibited.art_5_1_a.manipulation",
		"Art. 5(1)(a)",
		"critical",
		"The system deploys subliminal or purposefully manipulative techniques that distort behaviour and are liable to cause significant harm. This practice is prohibited outright in the EU.",
		"Withdraw this capability from the EU market. No documentation or consent mechanism makes an Art. 5 practice lawful.",
	)
}

violations contains v if {
	in_scope
	base.use_case == "vulnerability_exploitation"
	v := base.violation(
		"eu.prohibited.art_5_1_b.vulnerability_exploitation",
		"Art. 5(1)(b)",
		"critical",
		"The system exploits vulnerabilities arising from age, disability or social or economic situation in order to distort behaviour. This practice is prohibited outright in the EU.",
		"Withdraw this capability from the EU market and remove the targeting of vulnerable groups from the system's design.",
	)
}

# -----------------------------------------------------------------------------
# Art. 5(1)(c) — Social scoring
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.use_case == "social_scoring"
	v := base.violation(
		"eu.prohibited.art_5_1_c.social_scoring",
		"Art. 5(1)(c)",
		"critical",
		"The system evaluates or classifies people over time based on their social behaviour or personal characteristics, leading to detrimental treatment in unrelated contexts. Social scoring is prohibited in the EU.",
		"Withdraw the system from the EU market, or re-scope it so that scoring is confined to a single justified context and cannot produce detrimental treatment elsewhere.",
	)
}

# -----------------------------------------------------------------------------
# Art. 5(1)(d) — Individual predictive policing
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.use_case == "predictive_policing_individual"
	v := base.violation(
		"eu.prohibited.art_5_1_d.predictive_policing",
		"Art. 5(1)(d)",
		"critical",
		"The system predicts the risk of a natural person committing a criminal offence based solely on profiling or personality traits. This is prohibited; only systems supporting a human assessment already grounded in objective, verifiable facts fall outside the ban.",
		"Withdraw the system, or restrict it to supporting a human assessment that is based on objective and verifiable facts directly linked to a criminal activity.",
	)
}

# -----------------------------------------------------------------------------
# Art. 5(1)(e) — Untargeted scraping of facial images
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.use_case == "untargeted_face_scraping"
	v := base.violation(
		"eu.prohibited.art_5_1_e.face_scraping",
		"Art. 5(1)(e)",
		"critical",
		"The system creates or expands a facial recognition database through untargeted scraping of images from the internet or CCTV footage. This is prohibited in the EU.",
		"Stop the scraping, delete any database built from untargeted collection, and source biometric reference data only with a valid legal basis.",
	)
}

# -----------------------------------------------------------------------------
# Art. 5(1)(f) — Emotion recognition at work and in education
#
# Exempt where deployed for medical or safety reasons (for example fatigue
# detection for a driver). The exemption must be recorded to count.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	emotion_recognition_context
	not base.attribute("emotion_recognition_medical_or_safety_exemption")
	v := base.violation(
		"eu.prohibited.art_5_1_f.emotion_recognition",
		"Art. 5(1)(f)",
		"critical",
		"The system infers emotions of natural persons in a workplace or educational setting. Art. 5(1)(f) prohibits this except where it is put in place for medical or safety reasons, which is not recorded here.",
		"Discontinue emotion inference in workplace and education contexts. If the deployment is genuinely medical or safety related, document that basis and set attribute 'emotion_recognition_medical_or_safety_exemption' to true.",
	)
}

emotion_recognition_context if base.use_case == "emotion_recognition_workplace"

emotion_recognition_context if {
	base.use_case == "emotion_recognition"
	base.industry in {"hr_tech", "education", "employment", "recruitment"}
}

# -----------------------------------------------------------------------------
# Art. 5(1)(g) — Biometric categorisation inferring sensitive attributes
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.use_case == "biometric_categorisation"
	count(inferred_sensitive_attributes) > 0
	v := base.violation(
		"eu.prohibited.art_5_1_g.biometric_categorisation",
		"Art. 5(1)(g)",
		"critical",
		sprintf(
			"The system categorises people biometrically to infer sensitive attributes (%v). Art. 5(1)(g) prohibits inferring race, political opinions, trade union membership, religious or philosophical beliefs, sex life or sexual orientation from biometric data.",
			[concat(", ", sort(inferred_sensitive_attributes))],
		),
		"Remove inference of protected attributes from the system. Lawful biometric categorisation may not deduce these characteristics.",
	)
}

inferred_sensitive_attributes := base.data_categories & {
	"racial_origin",
	"ethnic_origin",
	"political_opinions",
	"religious_beliefs",
	"trade_union_membership",
	"sex_life",
	"sexual_orientation",
}

# -----------------------------------------------------------------------------
# Art. 5(1)(h) — Real-time remote biometric identification in public spaces
#
# Prohibited for law enforcement unless strictly necessary for one of the listed
# objectives and subject to prior judicial or independent administrative
# authorisation.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	realtime_remote_biometric_id
	base.industry in {"law_enforcement", "public_sector", "government"}
	not base.attribute("judicial_authorisation")
	v := base.violation(
		"eu.prohibited.art_5_1_h.realtime_biometric_id",
		"Art. 5(1)(h)",
		"critical",
		"Real-time remote biometric identification in publicly accessible spaces is used for law enforcement purposes without recorded prior authorisation. Art. 5(1)(h) prohibits this outside narrowly listed objectives authorised by a judicial or independent administrative authority.",
		"Suspend deployment until a prior authorisation covering each use is obtained and recorded, and set attribute 'judicial_authorisation' to true. Confirm the deployment falls within one of the exhaustively listed Art. 5(1)(h) objectives.",
	)
}

# Non-law-enforcement real-time identification in public spaces is not banned by
# Art. 5, but it is high-risk under Annex III and needs a legal basis under the
# GDPR — flagged so it is reviewed rather than assumed lawful.
violations contains v if {
	in_scope
	realtime_remote_biometric_id
	not base.industry in {"law_enforcement", "public_sector", "government"}
	not base.attribute("biometric_legal_basis_documented")
	v := base.violation(
		"eu.prohibited.art_5_1_h.biometric_legal_basis",
		"Art. 5(1)(h) / GDPR Art. 9",
		"high",
		"Real-time remote biometric identification is deployed in publicly accessible spaces outside a law-enforcement context with no legal basis recorded. This is not an Art. 5 prohibition, but processing biometric data at scale requires an Art. 9 GDPR condition and Annex III high-risk treatment.",
		"Record the GDPR Art. 9 condition relied on and the DPIA outcome, then set attribute 'biometric_legal_basis_documented' to true.",
	)
}

realtime_remote_biometric_id if {
	base.use_case == "biometric_identification"
	base.attribute("realtime_identification")
	base.attribute("publicly_accessible_space")
}
