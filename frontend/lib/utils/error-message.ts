import { ApiError, NetworkError } from "@/lib/api/client";

export interface ErrorCopy {
  title: string;
  description: string;
}

function formatResetTime(resetAt: string): string {
  try {
    const date = new Date(resetAt);
    return date.toLocaleString(undefined, {
      hour: "numeric",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "later";
  }
}

/** Turns any thrown error from the API layer into founder-facing copy
 * (D2) — a rate limit names its own limit and reset time rather than a
 * generic "something went wrong". */
export function describeError(error: unknown): ErrorCopy {
  if (error instanceof ApiError && error.rateLimit) {
    const { limit, scope, reset_at } = error.rateLimit;
    const scopeLabel = scope === "session" ? "this session" : "this network";
    return {
      title: "You've hit today's validation limit",
      description: `${scopeLabel === "this session" ? "You've" : "This network has"} used all ${limit} free validations for now. It resets around ${formatResetTime(reset_at)}.`,
    };
  }

  if (error instanceof ApiError && error.status === 404) {
    return {
      title: "Not found",
      description: "That page or idea doesn't exist, or you don't have access to it.",
    };
  }

  if (error instanceof ApiError && error.status === 422) {
    return {
      title: "That didn't validate",
      description: typeof error.detail === "string" ? error.detail : "Check the form and try again.",
    };
  }

  if (error instanceof ApiError && error.status >= 500) {
    return {
      title: "NotAFlop is having trouble",
      description: "Something went wrong on our end. Please try again in a moment.",
    };
  }

  if (error instanceof NetworkError) {
    return {
      title: "Connection lost",
      description: "Check your internet connection and try again.",
    };
  }

  if (error instanceof Error && error.name === "StreamConnectionError") {
    return {
      title: "Connection dropped",
      description: "The stream cut out before your verdict finished. We're checking whether it completed on our end.",
    };
  }

  return {
    title: "Something went wrong",
    description: error instanceof Error ? error.message : "Please try again.",
  };
}
