# =============================================================================
# EU AI Act — transparency obligations
# Regulation (EU) 2024/1689, Article 50 (plus Art. 52/53 GPAI duties)
#
# These duties attach to the *interaction*, not the risk tier: a minimal-risk
# chatbot still has to tell people they are talking to a machine. They apply in
# addition to any high-risk obligations, never instead of them.
#
# Severity is lower than the high-risk package by design. A missing disclosure is
# a real finding, but it is remediable in a sprint rather than blocking market
# placement, so most rules here are "medium" and surface as warnings.
# =============================================================================
package aigov.eu.transparency

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

severity_rank := {"critical": 4, "high": 3, "medium": 2, "low": 1}

severity := s if {
	count(violations) > 0
	top := max([severity_rank[v.severity] | some v in violations])
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
# Art. 50(1) — Disclosure of interaction with an AI system
#
# Waived only where it is obvious to a reasonably well-informed person. That
# judgement has to be recorded rather than assumed.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	interacts_with_people
	not base.attribute("ai_interaction_disclosed")
	not base.attribute("ai_interaction_obvious")
	v := base.violation(
		"eu.transparency.art_50_1.interaction_disclosure",
		"Art. 50(1)",
		"medium",
		"People interacting with this system are not told they are dealing with an AI system. Art. 50(1) requires that disclosure unless it is obvious from the circumstances to a reasonably well-informed person.",
		"Show a clear notice at the start of the interaction ('You are chatting with an AI assistant') and set attribute 'ai_interaction_disclosed' to true. If the AI nature is genuinely self-evident, record that judgement in 'ai_interaction_obvious'.",
	)
}

interacts_with_people if base.flag("uses_generative_ai")

interacts_with_people if base.attribute("direct_user_interaction")

interacts_with_people if base.use_case in {"chatbot", "customer_support", "virtual_assistant"}

# -----------------------------------------------------------------------------
# Art. 50(2) — Machine-readable marking of synthetic content
#
# The provider-side duty: output must be marked in a machine-readable format so
# it can be detected as artificially generated downstream.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.flag("uses_generative_ai")
	not base.attribute("synthetic_content_marked")
	v := base.violation(
		"eu.transparency.art_50_2.synthetic_content_marking",
		"Art. 50(2)",
		"high",
		"Generated output is not marked in a machine-readable way. Art. 50(2) requires providers of generative systems to mark synthetic audio, image, video or text so that it is detectable as artificially generated.",
		"Embed provenance metadata (for example C2PA Content Credentials) or watermarking in generated output, and set attribute 'synthetic_content_marked' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 50(3) — Emotion recognition and biometric categorisation notice
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	emotion_or_categorisation
	not base.attribute("biometric_processing_notice")
	v := base.violation(
		"eu.transparency.art_50_3.biometric_notice",
		"Art. 50(3)",
		"high",
		"People exposed to emotion recognition or biometric categorisation are not informed of that processing. Art. 50(3) requires deployers to inform the persons exposed and to process personal data in line with the GDPR.",
		"Inform exposed individuals before processing begins, document the GDPR legal basis, and set attribute 'biometric_processing_notice' to true.",
	)
}

emotion_or_categorisation if base.use_case in {"emotion_recognition", "biometric_categorisation"}

emotion_or_categorisation if {
	base.uses_biometrics
	base.flag("makes_automated_decisions")
}

# -----------------------------------------------------------------------------
# Art. 50(4) — Deep fake and public-interest text disclosure
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	base.attribute("generates_deepfakes")
	not base.attribute("deepfake_disclosure")
	v := base.violation(
		"eu.transparency.art_50_4.deepfake_disclosure",
		"Art. 50(4)",
		"high",
		"The system produces deep fake content without a disclosure that the material is artificially generated or manipulated. Art. 50(4) requires that disclosure for image, audio or video content resembling real people, places or events.",
		"Apply a visible disclosure to generated media and set attribute 'deepfake_disclosure' to true. Where the content is evidently artistic or satirical, the disclosure may be limited to a manner that does not hamper display of the work.",
	)
}

violations contains v if {
	in_scope
	base.flag("uses_generative_ai")
	base.attribute("publishes_public_interest_text")
	not base.attribute("editorial_human_review")
	v := base.violation(
		"eu.transparency.art_50_4.public_interest_text",
		"Art. 50(4)",
		"medium",
		"AI-generated text is published to inform the public on matters of public interest without disclosure or documented editorial review. Art. 50(4) requires disclosure unless the content underwent human review and someone holds editorial responsibility.",
		"Either disclose that the text is AI-generated, or record the human editorial review and the responsible editor, then set attribute 'editorial_human_review' to true.",
	)
}

# -----------------------------------------------------------------------------
# Art. 53 — General-purpose AI model duties passed down the value chain
#
# A deployer building on a third-party GPAI model needs the upstream provider's
# documentation and copyright/training-data summary to meet its own duties.
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	count(base.third_party_models) > 0
	not base.attribute("gpai_provider_documentation")
	v := base.violation(
		"eu.transparency.art_53.gpai_documentation",
		"Art. 53",
		"medium",
		sprintf(
			"This system builds on general-purpose models (%v) without the provider documentation on record. Art. 53 obliges GPAI providers to supply technical documentation and a sufficiently detailed summary of training content, which downstream deployers rely on.",
			[concat(", ", base.third_party_models)],
		),
		"Obtain and archive each model provider's technical documentation and public training-content summary, then set attribute 'gpai_provider_documentation' to true.",
	)
}

# -----------------------------------------------------------------------------
# Accessibility — Art. 50(5)
# -----------------------------------------------------------------------------

violations contains v if {
	in_scope
	notice_owed
	not base.attribute("accessible_disclosures")
	v := base.violation(
		"eu.transparency.art_50_5.accessible_format",
		"Art. 50(5)",
		"low",
		"Transparency notices are owed but no accessible format is recorded. Art. 50(5) requires the information to be provided clearly and to conform with the applicable accessibility requirements.",
		"Provide disclosures in an accessible format (screen-reader compatible, plain language, appropriate contrast) and set attribute 'accessible_disclosures' to true.",
	)
}

# Which notice duties apply at all. Derived from the same conditions as the rules
# above rather than from the violations set itself, which would be recursive.
notice_owed if interacts_with_people

notice_owed if emotion_or_categorisation

notice_owed if base.attribute("generates_deepfakes")
