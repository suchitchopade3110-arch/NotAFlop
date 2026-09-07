import { env } from "@/lib/env";
import { getStoredSessionId, useSessionStore } from "@/lib/store/session";
import type { ApiErrorBody, RateLimitErrorBody } from "@/types/api";

const SESSION_HEADER = "X-Session-Id";

function isRateLimitBody(value: unknown): value is RateLimitErrorBody {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return typeof v.limit === "number" && typeof v.remaining === "number" && typeof v.reset_at === "string";
}

/** Thrown by every apiFetch call on a non-2xx response. Carries the
 * parsed rate-limit body (A3) when the backend's 429 shape matches, so
 * callers can show "try again at 4:12pm" instead of a generic error. */
export class ApiError extends Error {
  status: number;
  detail: unknown;
  rateLimit: RateLimitErrorBody | null;

  constructor(status: number, detail: unknown) {
    const rateLimit = status === 429 && isRateLimitBody(detail) ? detail : null;
    const message =
      typeof detail === "string"
        ? detail
        : rateLimit
          ? `Rate limit exceeded (${rateLimit.scope}).`
          : `Request failed with status ${status}.`;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.rateLimit = rateLimit;
  }
}

export class NetworkError extends Error {
  constructor(message = "Could not reach NotAFlop. Check your connection and try again.") {
    super(message);
    this.name = "NetworkError";
  }
}

interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip attaching X-Session-Id (only the initial session mint needs to
   * omit it so the backend mints a fresh one rather than echoing null). */
  withSession?: boolean;
}

function buildHeaders(options: ApiFetchOptions): Headers {
  const headers = new Headers(options.headers);
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (options.withSession !== false) {
    const sessionId = getStoredSessionId();
    if (sessionId) headers.set(SESSION_HEADER, sessionId);
  }
  return headers;
}

function captureSessionHeader(response: Response): void {
  const sessionId = response.headers.get(SESSION_HEADER);
  if (sessionId && sessionId !== getStoredSessionId()) {
    useSessionStore.getState().setSessionId(sessionId);
  }
}

async function parseErrorBody(response: Response): Promise<unknown> {
  try {
    const json = (await response.json()) as ApiErrorBody;
    return json.detail ?? json;
  } catch {
    return response.statusText || "Request failed.";
  }
}

/** Core fetch wrapper — every /api and /v1 route call in this app goes
 * through this (except the SSE stream, which needs raw body access —
 * see lib/api/stream.ts). Attaches X-Session-Id, throws ApiError on any
 * non-2xx, and captures a server-minted session id from the response. */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const url = `${env.apiBaseUrl}${path}`;
  const headers = buildHeaders(options);
  const body =
    options.body === undefined
      ? undefined
      : options.body instanceof FormData
        ? options.body
        : JSON.stringify(options.body);

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers, body });
  } catch {
    throw new NetworkError();
  }

  captureSessionHeader(response);

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export { SESSION_HEADER };
