import { env } from "@/lib/env";
import { getStoredSessionId, useSessionStore } from "@/lib/store/session";
import { SESSION_HEADER } from "@/lib/api/client";
import type { StreamEvent } from "@/types/api";

export class StreamConnectionError extends Error {
  constructor(message = "The connection dropped before the analysis finished.") {
    super(message);
    this.name = "StreamConnectionError";
  }
}

interface StreamAnalyzeArgs {
  transcript: string;
  keyword?: string;
  signals: Record<string, unknown>;
  filterResult?: unknown;
  signal?: AbortSignal;
}

/**
 * POST /api/phase3/analyze streams Server-Sent Events, but it's a POST
 * with a JSON body and a custom session header — the browser's
 * EventSource only ever does GET with no custom headers, so this reads
 * the response body manually and re-implements minimal SSE framing
 * ("data: ...\n\n" lines, terminated by a literal "[DONE]" payload).
 *
 * Yields parsed StreamEvent objects as they arrive. Throws
 * StreamConnectionError if the connection drops before a "final" event
 * and the terminating [DONE] both landed — the caller (B3) is
 * responsible for degrading to a recoverable state, not this reader.
 */
export async function* streamAnalyze(args: StreamAnalyzeArgs): AsyncGenerator<StreamEvent, void, unknown> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const sessionId = getStoredSessionId();
  if (sessionId) headers.set(SESSION_HEADER, sessionId);

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}/api/phase3/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        transcript: args.transcript,
        keyword: args.keyword,
        signals: args.signals,
        filter_result: args.filterResult ?? null,
      }),
      signal: args.signal,
    });
  } catch {
    throw new StreamConnectionError("Could not reach NotAFlop to start the analysis.");
  }

  const returnedSessionId = response.headers.get(SESSION_HEADER);
  if (returnedSessionId && returnedSessionId !== getStoredSessionId()) {
    useSessionStore.getState().setSessionId(returnedSessionId);
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // non-JSON error body — keep statusText
    }
    if (response.status === 429) {
      const err = new Error(typeof detail === "string" ? detail : "Rate limit exceeded.");
      err.name = "RateLimitError";
      // @ts-expect-error — attach structured body for callers that care
      err.detail = detail;
      throw err;
    }
    throw new Error(typeof detail === "string" ? detail : "Analysis could not start.");
  }

  if (!response.body) {
    throw new StreamConnectionError("No response stream from server.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");

        const dataLine = rawEvent
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const data = dataLine.slice("data:".length).trim();

        if (data === "[DONE]") {
          sawDone = true;
          continue;
        }

        try {
          const parsed = JSON.parse(data) as StreamEvent;
          yield parsed;
        } catch {
          // Malformed frame — skip rather than kill the whole stream.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (!sawDone) {
    throw new StreamConnectionError();
  }
}
