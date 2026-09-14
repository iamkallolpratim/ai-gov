# Global baseline — generative AI transparency, applied across jurisdictions.
package aigov.global.transparency

import rego.v1

default allow := false

allow if {
	count(violations) == 0
}

violations contains v if {
	input.metadata.uses_generative_ai
	not input.metadata.attributes.ai_content_labelled
	v := {
		"rule": "genai_content_labelling",
		"msg": "Generative output must be machine-readably marked as AI-generated.",
		"remediation": "Enable content provenance marking (e.g. C2PA) and set metadata attribute 'ai_content_labelled' to true.",
	}
}

violations contains v if {
	input.metadata.makes_automated_decisions
	not input.metadata.attributes.subject_notice_provided
	v := {
		"rule": "automated_decision_notice",
		"msg": "Individuals subject to automated decisions must be informed that AI is being used.",
		"remediation": "Publish a notice at the point of decision and set metadata attribute 'subject_notice_provided' to true.",
	}
}

violations contains v if {
	count(input.metadata.third_party_models) > 0
	not input.metadata.attributes.vendor_dpa_signed
	v := {
		"rule": "third_party_model_diligence",
		"msg": "Third-party model providers require a signed data processing agreement.",
		"remediation": "Execute a DPA with each model vendor and set metadata attribute 'vendor_dpa_signed' to true.",
	}
}
