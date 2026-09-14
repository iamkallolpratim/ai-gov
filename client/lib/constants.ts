import type { AutonomyLevel, PolicySeverity, RiskTier, SystemStatus } from "@/types/api";

/**
 * Vocabularies the backend actually recognises.
 *
 * These strings are not cosmetic: `use_case` drives Annex III matching in the EU policy
 * package, and the region codes drive jurisdiction detection. Offering the real values
 * as suggestions is the difference between a system being classified correctly and
 * silently falling out of scope. Free text is still allowed everywhere.
 */

export const USE_CASES: { value: string; label: string; group: string }[] = [
  { value: "employment_screening", label: "Employment screening", group: "Annex III · Employment" },
  { value: "worker_management", label: "Worker management", group: "Annex III · Employment" },
  { value: "performance_evaluation", label: "Performance evaluation", group: "Annex III · Employment" },
  { value: "credit_scoring", label: "Credit scoring", group: "Annex III · Essential services" },
  { value: "insurance_underwriting", label: "Insurance underwriting", group: "Annex III · Essential services" },
  { value: "benefits_eligibility", label: "Benefits eligibility", group: "Annex III · Essential services" },
  { value: "essential_services", label: "Essential services access", group: "Annex III · Essential services" },
  { value: "emergency_triage", label: "Emergency triage", group: "Annex III · Essential services" },
  { value: "education_assessment", label: "Education assessment", group: "Annex III · Education" },
  { value: "exam_proctoring", label: "Exam proctoring", group: "Annex III · Education" },
  { value: "biometric_identification", label: "Biometric identification", group: "Annex III · Biometrics" },
  { value: "biometric_categorisation", label: "Biometric categorisation", group: "Annex III · Biometrics" },
  { value: "emotion_recognition", label: "Emotion recognition", group: "Annex III · Biometrics" },
  { value: "law_enforcement", label: "Law enforcement", group: "Annex III · Law enforcement" },
  { value: "crime_risk_assessment", label: "Crime risk assessment", group: "Annex III · Law enforcement" },
  { value: "migration_asylum", label: "Migration and asylum", group: "Annex III · Border" },
  { value: "border_control", label: "Border control", group: "Annex III · Border" },
  { value: "judicial_decision_support", label: "Judicial decision support", group: "Annex III · Justice" },
  { value: "critical_infrastructure", label: "Critical infrastructure", group: "Annex III · Infrastructure" },
  { value: "medical_diagnosis", label: "Medical diagnosis", group: "Annex III · Health" },
  { value: "social_scoring", label: "Social scoring", group: "Art. 5 · Prohibited" },
  { value: "subliminal_manipulation", label: "Subliminal manipulation", group: "Art. 5 · Prohibited" },
  { value: "emotion_recognition_workplace", label: "Emotion recognition (workplace)", group: "Art. 5 · Prohibited" },
  { value: "untargeted_face_scraping", label: "Untargeted face scraping", group: "Art. 5 · Prohibited" },
  { value: "predictive_policing_individual", label: "Predictive policing (individual)", group: "Art. 5 · Prohibited" },
  { value: "customer_support", label: "Customer support", group: "General purpose" },
  { value: "chatbot", label: "Chatbot / assistant", group: "General purpose" },
  { value: "content_ranking", label: "Content ranking", group: "General purpose" },
  { value: "demand_forecasting", label: "Demand forecasting", group: "General purpose" },
  { value: "predictive_maintenance", label: "Predictive maintenance", group: "General purpose" },
  { value: "fraud_detection", label: "Fraud detection", group: "General purpose" },
];

export const REGIONS: { value: string; label: string }[] = [
  { value: "GLOBAL", label: "GLOBAL — anywhere / public internet" },
  { value: "EU", label: "EU — European Union" },
  { value: "EEA", label: "EEA — European Economic Area" },
  { value: "US-CA", label: "US-CA — California" },
  { value: "US-NY", label: "US-NY — New York" },
  { value: "US-CO", label: "US-CO — Colorado" },
  { value: "US", label: "US — United States" },
  { value: "CN", label: "CN — China" },
  { value: "IN", label: "IN — India" },
  { value: "GB", label: "GB — United Kingdom" },
  { value: "DE", label: "DE — Germany" },
  { value: "FR", label: "FR — France" },
  { value: "IE", label: "IE — Ireland" },
  { value: "NL", label: "NL — Netherlands" },
  { value: "ES", label: "ES — Spain" },
  { value: "BR", label: "BR — Brazil" },
  { value: "CA-COUNTRY", label: "CA-COUNTRY — Canada" },
];

export const DATA_CATEGORIES: { value: string; label: string; sensitive?: boolean }[] = [
  { value: "personal_data", label: "Personal data" },
  { value: "employment_history", label: "Employment history" },
  { value: "financial", label: "Financial" },
  { value: "operational_data", label: "Operational data" },
  { value: "support_tickets", label: "Support tickets" },
  { value: "biometric", label: "Biometric", sensitive: true },
  { value: "health", label: "Health", sensitive: true },
  { value: "genetic", label: "Genetic", sensitive: true },
  { value: "racial_origin", label: "Racial origin", sensitive: true },
  { value: "ethnic_origin", label: "Ethnic origin", sensitive: true },
  { value: "political_opinions", label: "Political opinions", sensitive: true },
  { value: "religious_beliefs", label: "Religious beliefs", sensitive: true },
  { value: "trade_union_membership", label: "Trade union membership", sensitive: true },
  { value: "sex_life", label: "Sex life", sensitive: true },
  { value: "sexual_orientation", label: "Sexual orientation", sensitive: true },
  { value: "criminal_convictions", label: "Criminal convictions", sensitive: true },
  { value: "children", label: "Children's data", sensitive: true },
];

export const INDUSTRIES = [
  "hr_tech", "fintech", "insurance", "healthcare", "education", "retail", "logistics",
  "saas", "public_sector", "government", "law_enforcement", "telecom", "energy", "other",
];

export const AUTONOMY_LABELS: Record<AutonomyLevel, string> = {
  human_in_the_loop: "Human in the loop",
  human_on_the_loop: "Human on the loop",
  fully_autonomous: "Fully autonomous",
};

export const RISK_TIER_LABELS: Record<RiskTier, string> = {
  prohibited: "Prohibited",
  high: "High risk",
  limited: "Limited risk",
  minimal: "Minimal risk",
  unknown: "Unclassified",
};

export const STATUS_LABELS: Record<SystemStatus, string> = {
  draft: "Draft",
  active: "Active",
  retired: "Retired",
};

export const SEVERITY_LABELS: Record<PolicySeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

/**
 * Governance controls the shipped EU AI Act policies read. Grouped so the form explains
 * *why* a field matters rather than presenting 12 anonymous switches.
 */
export const GOVERNANCE_CONTROLS: {
  name: keyof import("@/types/api").SystemMetadata;
  label: string;
  help: string;
}[] = [
  { name: "human_oversight_documented", label: "Human oversight documented", help: "EU AI Act Art. 14" },
  { name: "conformity_assessment_done", label: "Conformity assessment completed", help: "Art. 43" },
  { name: "training_data_documented", label: "Training data documented", help: "Art. 10" },
  { name: "incident_response_plan", label: "Incident response plan", help: "Art. 73" },
  { name: "makes_automated_decisions", label: "Makes automated decisions", help: "Drives consequential-decision rules" },
  { name: "uses_biometrics", label: "Processes biometric data", help: "Art. 5(1)(h), Art. 15(5)" },
  { name: "uses_generative_ai", label: "Generative AI", help: "Art. 50 transparency duties" },
  { name: "affects_minors", label: "Affects minors", help: "Raises duties in most regimes" },
  { name: "is_safety_component", label: "Safety component of a product", help: "Art. 6 high-risk trigger" },
];

/** Attribute flags the EU packages read out of `metadata.attributes`. */
export const ATTRIBUTE_FLAGS: { name: string; label: string; help: string }[] = [
  { name: "risk_management_system", label: "Risk management system", help: "Art. 9" },
  { name: "automatic_logging_enabled", label: "Automatic logging enabled", help: "Art. 12" },
  { name: "instructions_for_use", label: "Instructions for use published", help: "Art. 13" },
  { name: "accuracy_metrics_declared", label: "Accuracy metrics declared", help: "Art. 15" },
  { name: "human_review_of_individual_decisions", label: "Individual decision review", help: "Art. 14" },
  { name: "human_override_capability", label: "Human override capability", help: "Art. 14(4)" },
  { name: "eu_database_registered", label: "Registered in EU database", help: "Art. 49" },
  { name: "post_market_monitoring_plan", label: "Post-market monitoring plan", help: "Art. 72" },
  { name: "fundamental_rights_impact_assessment", label: "Fundamental rights impact assessment", help: "Art. 27" },
  { name: "special_category_safeguards", label: "Special category safeguards", help: "Art. 10(5)" },
  { name: "ai_interaction_disclosed", label: "AI interaction disclosed", help: "Art. 50(1)" },
  { name: "synthetic_content_marked", label: "Synthetic content marked", help: "Art. 50(2)" },
  { name: "upstream_provider_agreement", label: "Upstream provider agreement", help: "Art. 25" },
  { name: "gpai_provider_documentation", label: "GPAI provider documentation", help: "Art. 53" },
];
