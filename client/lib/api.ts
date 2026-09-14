/**
 * The single integration point with the FastAPI backend.
 *
 * Responsibilities kept here so no component ever builds a URL or unwraps a payload:
 *  - prefix the base URL and attach the bearer token
 *  - unwrap the `{success, data}` envelope every `/api/v1` route returns
 *  - turn `{success: false, error}` into a typed `ApiError`
 *  - refresh an expired access token once, single-flight, and retry the request
 */

import { ApiError, NetworkError } from "@/lib/errors";
import type {
  AISystem,
  AISystemCreateInput,
  AISystemUpdateInput,
  AuditLog,
  AuditLogParams,
  AuthMode,
  ClassificationResponse,
  DashboardSummary,
  EvidenceAccepted,
  EvidenceGenerateInput,
  EvidencePackage,
  Jurisdiction,
  JurisdictionDashboard,
  JurisdictionDetection,
  Page,
  PendingReview,
  Policy,
  PolicyCheck,
  PolicyCheckRun,
  RecentFailure,
  RiskClassification,
  SystemListParams,
  SystemVersion,
  TokenResponse,
  User,
  UserCreateInput,
} from "@/types/api";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const V1 = "/api/v1";

// --- token access ----------------------------------------------------------
// The auth store owns the tokens. It registers these accessors on creation, which keeps
// this module free of a circular import back into the store.

type TokenBundle = { accessToken: string | null; refreshToken: string | null };

let tokenAccessor: () => TokenBundle = () => ({ accessToken: null, refreshToken: null });
let onTokensRefreshed: (tokens: TokenResponse) => void = () => {};
let onAuthFailure: () => void = () => {};

export function registerAuthBridge(bridge: {
  getTokens: () => TokenBundle;
  setTokens: (tokens: TokenResponse) => void;
  onFailure: () => void;
}) {
  tokenAccessor = bridge.getTokens;
  onTokensRefreshed = bridge.setTokens;
  onAuthFailure = bridge.onFailure;
}

// --- query strings ---------------------------------------------------------

type QueryValue = string | number | boolean | null | undefined | (string | number)[];

/**
 * Arrays are emitted as repeated keys (`?status=draft&status=active`), which is what
 * FastAPI expects for `list[...]` query params — not a comma-joined string.
 */
export function buildQuery(params: Record<string, QueryValue> = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") search.append(key, String(item));
      }
    } else {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// --- core fetch ------------------------------------------------------------

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Ops endpoints (`/health`, `/ready`) return a bare payload, not the envelope. */
  raw?: boolean;
  /** Internal: prevents a refresh loop when the refresh call itself 401s. */
  skipRefresh?: boolean;
}

let refreshInFlight: Promise<boolean> | null = null;

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function errorFromBody(status: number, body: unknown, fallbackRequestId: string | null): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const err = (body as { error: { code?: string; message?: string; details?: unknown; request_id?: string | null } }).error;
    return new ApiError({
      status,
      code: err?.code ?? "UNKNOWN",
      message: err?.message ?? "Request failed.",
      details: err?.details,
      requestId: err?.request_id ?? fallbackRequestId,
    });
  }
  const message =
    typeof body === "string" && body ? body : `Request failed with status ${status}.`;
  return new ApiError({ status, code: "UNKNOWN", message, requestId: fallbackRequestId });
}

async function attemptRefresh(): Promise<boolean> {
  const { refreshToken } = tokenAccessor();
  if (!refreshToken) return false;

  // Single-flight: several parallel 401s must trigger exactly one refresh.
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}${V1}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) return false;
        const body = (await response.json()) as { data?: TokenResponse };
        if (!body?.data?.access_token) return false;
        onTokensRefreshed(body.data);
        return true;
      } catch {
        return false;
      } finally {
        // Cleared on the next tick so concurrent callers all observe this result.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, raw = false, skipRefresh = false, headers, ...init } = options;
  const { accessToken } = tokenAccessor();

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (body !== undefined) requestHeaders.set("Content-Type", "application/json");
  if (accessToken) requestHeaders.set("Authorization", `Bearer ${accessToken}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new NetworkError();
  }

  const requestId = response.headers.get("X-Request-ID");

  // Expired access token: refresh once, then replay the original request.
  if (response.status === 401 && !skipRefresh && !path.includes("/auth/refresh")) {
    if (await attemptRefresh()) {
      return apiFetch<T>(path, { ...options, skipRefresh: true });
    }
    onAuthFailure();
  }

  const payload = await parseBody(response);

  if (!response.ok) throw errorFromBody(response.status, payload, requestId);
  if (response.status === 204 || payload === null) return undefined as T;
  if (raw) return payload as T;

  // Success envelope: `{success: true, data: ...}`.
  if (payload && typeof payload === "object" && "success" in payload && "data" in payload) {
    return (payload as { data: T }).data;
  }
  // An unwrapped 2xx body still round-trips, so ops endpoints work without `raw`.
  return payload as T;
}

// --- resource helpers ------------------------------------------------------

export const api = {
  auth: {
    mode: () => apiFetch<AuthMode>(`${V1}/auth/mode`),
    login: (email: string, password: string) =>
      apiFetch<TokenResponse>(`${V1}/auth/login`, {
        method: "POST",
        body: { email, password },
      }),
    me: () => apiFetch<User>(`${V1}/auth/me`),
    users: (params: { page?: number; page_size?: number } = {}) =>
      apiFetch<Page<User>>(`${V1}/auth/users${buildQuery(params)}`),
    createUser: (input: UserCreateInput) =>
      apiFetch<User>(`${V1}/auth/users`, { method: "POST", body: input }),
    updateUser: (id: string, input: Partial<UserCreateInput> & { is_active?: boolean }) =>
      apiFetch<User>(`${V1}/auth/users/${id}`, { method: "PATCH", body: input }),
  },

  systems: {
    list: (params: SystemListParams = {}) =>
      apiFetch<Page<AISystem>>(`${V1}/systems${buildQuery(params as Record<string, QueryValue>)}`),
    get: (id: string) => apiFetch<AISystem>(`${V1}/systems/${id}`),
    create: (input: AISystemCreateInput) =>
      apiFetch<AISystem>(`${V1}/systems`, { method: "POST", body: input }),
    update: (id: string, input: AISystemUpdateInput) =>
      apiFetch<AISystem>(`${V1}/systems/${id}`, { method: "PATCH", body: input }),
    remove: (id: string) => apiFetch<void>(`${V1}/systems/${id}`, { method: "DELETE" }),
    restore: (id: string) => apiFetch<AISystem>(`${V1}/systems/${id}/restore`, { method: "POST" }),
    versions: (id: string) => apiFetch<SystemVersion[]>(`${V1}/systems/${id}/versions`),

    classify: (id: string, input: { jurisdictions?: string[] | null; force?: boolean } = {}) =>
      apiFetch<ClassificationResponse>(`${V1}/systems/${id}/classify`, {
        method: "POST",
        body: input,
      }),
    classifications: (id: string, params: { jurisdiction?: string; latest_only?: boolean } = {}) =>
      apiFetch<RiskClassification[]>(`${V1}/systems/${id}/classifications${buildQuery(params)}`),

    checkPolicies: (
      id: string,
      input: { jurisdictions?: string[] | null; policy_keys?: string[] | null; reclassify?: boolean } = {},
    ) =>
      apiFetch<PolicyCheckRun>(`${V1}/systems/${id}/check-policies`, {
        method: "POST",
        body: { reclassify: true, ...input },
      }),
    policyChecks: (id: string, params: { latest_only?: boolean; page?: number; page_size?: number } = {}) =>
      apiFetch<Page<PolicyCheck>>(`${V1}/systems/${id}/policy-checks${buildQuery(params)}`),

    evidence: (id: string, params: { page?: number; page_size?: number } = {}) =>
      apiFetch<Page<EvidencePackage>>(`${V1}/systems/${id}/evidence${buildQuery(params)}`),
    evidencePackage: (systemId: string, packageId: string) =>
      apiFetch<EvidencePackage>(`${V1}/systems/${systemId}/evidence/${packageId}`),
    generateEvidence: (id: string, input: EvidenceGenerateInput = {}) =>
      apiFetch<EvidenceAccepted>(`${V1}/systems/${id}/evidence`, { method: "POST", body: input }),
    retryEvidence: (systemId: string, packageId: string) =>
      apiFetch<EvidenceAccepted>(`${V1}/systems/${systemId}/evidence/${packageId}/retry`, {
        method: "POST",
      }),
  },

  dashboard: {
    summary: (refresh = false) =>
      apiFetch<DashboardSummary>(`${V1}/dashboard/summary${buildQuery({ refresh })}`),
    byJurisdiction: (refresh = false) =>
      apiFetch<JurisdictionDashboard>(`${V1}/dashboard/by-jurisdiction${buildQuery({ refresh })}`),
    recentFailures: (limit = 20) =>
      apiFetch<RecentFailure[]>(`${V1}/dashboard/recent-failures${buildQuery({ limit })}`),
    pendingReviews: (limit = 20) =>
      apiFetch<PendingReview[]>(`${V1}/dashboard/pending-reviews${buildQuery({ limit })}`),
  },

  jurisdictions: {
    list: (isActive?: boolean) =>
      apiFetch<Jurisdiction[]>(`${V1}/jurisdictions${buildQuery({ is_active: isActive })}`),
    get: (code: string) => apiFetch<Jurisdiction>(`${V1}/jurisdictions/${code}`),
    detect: (systemId: string, includeInapplicable = true) =>
      apiFetch<JurisdictionDetection>(
        `${V1}/jurisdictions/detect/${systemId}${buildQuery({ include_inapplicable: includeInapplicable })}`,
      ),
  },

  policies: {
    list: (params: { jurisdiction?: string; is_active?: boolean; page?: number; page_size?: number } = {}) =>
      apiFetch<Page<Policy>>(`${V1}/policies${buildQuery(params)}`),
    get: (id: string) => apiFetch<Policy>(`${V1}/policies/${id}`),
  },

  auditLogs: {
    list: (params: AuditLogParams = {}) =>
      apiFetch<Page<AuditLog>>(`${V1}/audit-logs${buildQuery(params as Record<string, QueryValue>)}`),
    get: (id: string) => apiFetch<AuditLog>(`${V1}/audit-logs/${id}`),
  },

  ops: {
    ready: () =>
      apiFetch<{ status: string; checks: Record<string, boolean>; auth_enabled: boolean }>("/ready", {
        raw: true,
      }),
  },
};
