/** Error thrown by the API client for any non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(opts: {
    status: number;
    code: string;
    message: string;
    details?: unknown;
    requestId?: string | null;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.details = opts.details ?? {};
    this.requestId = opts.requestId ?? null;
  }

  get isAuth() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isNotFound() {
    return this.status === 404;
  }
  get isRateLimited() {
    return this.status === 429;
  }
  get isServer() {
    return this.status >= 500;
  }
}

/** Network-level failure: the backend could not be reached at all. */
export class NetworkError extends Error {
  constructor(message = "Could not reach the API.") {
    super(message);
    this.name = "NetworkError";
  }
}

/**
 * Message shown to the user. Backend messages are written for humans, so they are used
 * as-is; these only add context the API cannot know (which limit was hit, that the
 * server is unreachable rather than broken).
 */
export function toUserMessage(error: unknown): string {
  if (error instanceof NetworkError) {
    return "Could not reach the API. Is the backend running?";
  }
  if (error instanceof ApiError) {
    switch (error.code) {
      case "RATE_LIMITED":
        return `${error.message} Evidence generation is limited to 20/hour and policy checks to 60/hour.`;
      case "FORBIDDEN":
        return error.message || "Your role does not allow this action.";
      case "UNAUTHORIZED":
        return error.message || "Your session has expired. Please sign in again.";
      case "VALIDATION_ERROR":
        return error.message || "Some fields need attention.";
      default:
        return error.message || "Something went wrong.";
    }
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

/** Field-level messages from a FastAPI 422, keyed by field name. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "VALIDATION_ERROR") return {};
  const details = error.details as { errors?: { loc?: unknown[]; msg?: string }[] } | undefined;
  const out: Record<string, string> = {};
  for (const item of details?.errors ?? []) {
    const loc = (item.loc ?? []).filter((p) => p !== "body");
    if (loc.length && item.msg) out[loc.join(".")] = item.msg;
  }
  return out;
}
