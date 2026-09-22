/**
 * Types mirroring the FastAPI backend's OpenAPI schema.
 *
 * Kept hand-written rather than generated so the shapes stay readable, but they are a
 * faithful copy of `/openapi.json` — if the backend changes, update this file first.
 */

// --- enums -----------------------------------------------------------------

export const RISK_TIERS = ["prohibited", "high", "limited", "minimal", "unknown"] as const;
export type RiskTier = (typeof RISK_TIERS)[number];

export const POLICY_RESULTS = ["pass", "fail", "warning", "error"] as const;
export type PolicyResult = (typeof POLICY_RESULTS)[number];

export const POLICY_SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
export type PolicySeverity = (typeof POLICY_SEVERITIES)[number];

export const SYSTEM_STATUSES = ["draft", "active", "retired"] as const;
export type SystemStatus = (typeof SYSTEM_STATUSES)[number];

export const USER_ROLES = ["admin", "risk_officer", "viewer"] as const;
export type UserRole = (typeof USER_ROLES)[number];

export const EVIDENCE_STATUSES = ["pending", "running", "completed", "failed"] as const;
export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];

export const AUTONOMY_LEVELS = [
  "human_in_the_loop",
  "human_on_the_loop",
  "fully_autonomous",
] as const;
export type AutonomyLevel = (typeof AUTONOMY_LEVELS)[number];

export const AUDIT_ACTIONS = [
  "create",
  "update",
  "delete",
  "classify",
  "policy_check",
  "evidence_generate",
  "login",
  "login_failed",
  "read",
] as const;
export type AuditAction = (typeof AUDIT_ACTIONS)[number];

export type ActorType = "user" | "system";

// --- envelope --------------------------------------------------------------

/** Every `/api/v1` response is wrapped in this envelope. */
export interface SuccessEnvelope<T> {
  success: true;
  data: T;
}

export interface ErrorEnvelope {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
    request_id?: string | null;
  };
}

export interface PageMeta {
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

// --- auth ------------------------------------------------------------------

export interface AuthMode {
  auth_enabled: boolean;
  auth_disabled: boolean;
  access_token_expires_in: number;
  refresh_token_expires_in: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  /** True for the synthetic principal used when the server runs with AUTH_DISABLED. */
  is_system?: boolean;
  created_at: string;
}

export interface UserCreateInput {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
}

// --- systems ---------------------------------------------------------------

export interface SystemMetadata {
  purpose?: string | null;
  use_case?: string | null;
  industry?: string | null;
  autonomy_level?: AutonomyLevel;
  data_categories?: string[];
  deployment_regions?: string[];
  data_subject_regions?: string[];
  data_residency?: string[];
  offered_in_regions?: string[];
  service_accessible_regions?: string[];
  content_accessible_regions?: string[];
  third_party_models?: string[];
  affects_minors?: boolean;
  uses_biometrics?: boolean;
  uses_generative_ai?: boolean;
  is_safety_component?: boolean;
  makes_automated_decisions?: boolean;
  human_oversight_documented?: boolean;
  conformity_assessment_done?: boolean;
  technical_documentation_url?: string | null;
  training_data_documented?: boolean;
  incident_response_plan?: boolean;
  attributes?: Record<string, unknown>;
}

export interface SystemMetadataRead extends SystemMetadata {
  id: string;
  updated_at: string;
}

export interface Owner {
  id: string;
  email: string;
  full_name: string;
}

export interface AISystem {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  owner?: Owner | null;
  status: SystemStatus;
  metadata_version: number;
  metadata: Record<string, unknown>;
  system_metadata?: SystemMetadataRead | null;
  created_at: string;
  updated_at: string;
}

export interface AISystemCreateInput {
  name: string;
  description?: string | null;
  owner_id?: string | null;
  status?: SystemStatus;
  metadata?: Record<string, unknown>;
  system_metadata?: SystemMetadata;
}

export interface AISystemUpdateInput extends Partial<AISystemCreateInput> {
  change_summary?: string;
}

export interface SystemVersion {
  id: string;
  version: number;
  changed_by_id: string | null;
  change_summary: string | null;
  snapshot: Record<string, unknown>;
  diff: Record<string, unknown>;
  created_at: string;
}

export interface SystemListParams {
  q?: string;
  status?: SystemStatus[];
  owner_id?: string;
  jurisdiction?: string[];
  risk_tier?: RiskTier[];
  industry?: string;
  use_case?: string;
  deployment_region?: string;
  uses_generative_ai?: boolean;
  include_deleted?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

// --- jurisdictions and risk ------------------------------------------------

export interface JurisdictionMatch {
  code: string;
  name: string;
  regulation_name?: string | null;
  applicable?: boolean;
  confidence: number;
  reasons: string[];
  signals?: string[];
  matched_territories?: string[];
  strictness?: number;
}

export interface JurisdictionDetection {
  ai_system_id: string;
  matches: JurisdictionMatch[];
  applicable_jurisdictions?: string[];
  evaluation_order?: string[];
  most_restrictive_jurisdictions?: string[];
  apply_most_restrictive?: boolean;
  conflict_notes?: string[];
  most_restrictive?: string | null;
  evaluated_at: string;
}

/** Shape of `RiskClassification.details`, which the API types only as an object. */
export interface RiskClassificationDetails {
  baseline?: {
    score?: number;
    tier?: string;
    signals?: { signal: string; weight: number; rationale: string }[];
    notes?: string[];
  };
  overlay?: {
    notes?: string[];
    tier_label?: string;
    obligations?: string[];
  };
  jurisdiction?: {
    confidence?: number;
    signals?: string[];
    matched_territories?: string[];
    strictness?: number;
    evaluation_order?: string[];
    most_restrictive?: string[];
    apply_most_restrictive?: boolean;
  };
  engine_version?: string;
}

export interface RiskClassification {
  id: string;
  ai_system_id: string;
  jurisdiction_code: string;
  risk_tier: RiskTier;
  score: number;
  is_applicable: boolean;
  applicability_reasons: string[];
  metadata_version: number;
  evaluated_at: string;
  evaluated_by_id: string | null;
  details: RiskClassificationDetails;
}

export interface ClassificationResponse {
  ai_system_id: string;
  jurisdictions: JurisdictionDetection;
  detected_jurisdictions: JurisdictionMatch[];
  classifications: RiskClassification[];
  most_restrictive_tier: RiskTier;
  most_restrictive_jurisdiction: string | null;
  evaluated_at: string;
}

export interface Jurisdiction {
  id: string;
  code: string;
  name: string;
  regulation_name?: string | null;
  description?: string | null;
  is_active: boolean;
  territories: string[];
  risk_taxonomy: Record<string, unknown>;
  overlay_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// --- policies --------------------------------------------------------------

export interface PolicyViolation {
  rule_id: string;
  article?: string | null;
  severity: PolicySeverity;
  msg: string;
  remediation?: string | null;
  /** "not_in_force" marks a readiness finding: a bill, or an act before its effective date. */
  status?: "in_force" | "not_in_force";
  /** RFC 3339 date the obligation takes effect, or "pending" for a bill with no date. */
  effective_date?: string;
  /** The instrument cited, e.g. "SB 24-205" or "PL 2338/2023". */
  source?: string;
  [key: string]: unknown;
}

export interface PolicyCheck {
  id: string;
  ai_system_id: string;
  policy_id: string;
  policy_key: string;
  policy_version: string;
  jurisdiction_code: string;
  severity: PolicySeverity;
  result: PolicyResult;
  explanation: string;
  violations: PolicyViolation[];
  remediation: string[];
  raw_opa_response: Record<string, unknown>;
  engine: string;
  checked_at: string;
  checked_by_id: string | null;
}

export interface PolicyCheckSummary {
  total: number;
  passed: number;
  failed: number;
  warnings: number;
  errors: number;
  compliant: boolean;
}

export interface PolicyCheckRun {
  ai_system_id: string;
  summary: PolicyCheckSummary;
  checks: PolicyCheck[];
  checked_at: string;
}

export interface Policy {
  id: string;
  key: string;
  name: string;
  description?: string | null;
  jurisdiction_code: string;
  version: string;
  severity: PolicySeverity;
  opa_package: string;
  rego_code?: string | null;
  rules: Record<string, unknown>;
  remediation?: string | null;
  applies_to_risk_tiers: RiskTier[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// --- evidence --------------------------------------------------------------

export interface EvidencePackage {
  id: string;
  ai_system_id: string;
  jurisdictions: string[];
  status: EvidenceStatus;
  task_id: string | null;
  file_url: string | null;
  json_url: string | null;
  checksum_sha256: string | null;
  error_message: string | null;
  summary: Record<string, unknown> & Partial<PolicyCheckSummary>;
  generated_at: string | null;
  generated_by_id: string | null;
  created_at: string;
  /** Last queue, retry or worker start. Staleness is measured from this. */
  updated_at: string;
}

export interface EvidenceAccepted {
  package_id: string;
  task_id: string | null;
  status: EvidenceStatus;
  poll_url: string;
}

export interface EvidenceGenerateInput {
  jurisdictions?: string[] | null;
  include_policy_checks?: boolean;
  include_history?: boolean;
  refresh_checks?: boolean;
  notes?: string | null;
}

// --- dashboard -------------------------------------------------------------

export interface RiskTierCount {
  risk_tier: RiskTier;
  count: number;
}

export interface RecentFailure {
  check_id: string;
  ai_system_id: string;
  ai_system_name: string;
  policy_key: string;
  policy_name: string;
  jurisdiction_code: string;
  severity: PolicySeverity;
  result: PolicyResult;
  explanation: string;
  checked_at: string;
}

export interface PendingReview {
  ai_system_id: string;
  ai_system_name: string;
  status: SystemStatus;
  reason: string;
  last_evaluated_at: string | null;
}

export interface DashboardSummary {
  total_systems: number;
  active_systems: number;
  draft_systems: number;
  retired_systems: number;
  systems_assessed: number;
  systems_never_assessed: number;
  overall_compliance_score: number;
  risk_tiers: RiskTierCount[];
  jurisdictions_in_scope: number;
  open_failures: number;
  critical_failures: number;
  evidence_packages_30d: number;
  recent_failures: RecentFailure[];
  pending_reviews: PendingReview[];
  generated_at: string;
}

export interface JurisdictionCompliance {
  jurisdiction_code: string;
  jurisdiction_name: string;
  systems_in_scope: number;
  compliant_systems: number;
  non_compliant_systems: number;
  unassessed_systems: number;
  compliance_rate: number;
  risk_tiers: RiskTierCount[];
  open_failures: number;
  critical_failures: number;
}

export interface JurisdictionDashboard {
  jurisdictions: JurisdictionCompliance[];
  generated_at: string;
}

// --- audit -----------------------------------------------------------------

export interface AuditLog {
  id: string;
  resource_type: string;
  resource_id: string | null;
  action: AuditAction;
  actor_id: string | null;
  actor_email: string | null;
  actor_type: ActorType;
  actor_label: string;
  request_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  old_values: Record<string, unknown>;
  new_values: Record<string, unknown>;
  context: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogParams {
  resource_type?: string;
  resource_id?: string;
  action?: AuditAction;
  actor_id?: string;
  actor_type?: ActorType;
  request_id?: string;
  since?: string;
  until?: string;
  page?: number;
  page_size?: number;
}
