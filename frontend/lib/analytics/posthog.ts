import posthog from "posthog-js";
import { env } from "@/lib/env";

let initialized = false;

export function initAnalytics(): void {
  if (initialized || typeof window === "undefined" || !env.posthogKey) return;
  posthog.init(env.posthogKey, {
    api_host: env.posthogHost,
    // We call capture() ourselves for a deliberate funnel (D1) — no
    // autocapture of clicks/inputs, which would risk vacuuming up pitch
    // text or an email typed into a field.
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    persistence: "localStorage",
  });
  initialized = true;
}

// Keys that must never leave this device in an analytics payload, even
// by accident — checked defensively on every capture() call below, on
// top of every call site already being written not to pass them.
const FORBIDDEN_KEY_PATTERN = /pitch|transcript|email|evidence|payload|raw_text|address/i;

function stripForbidden(properties: Record<string, unknown>): Record<string, unknown> {
  const safe: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(properties)) {
    if (FORBIDDEN_KEY_PATTERN.test(key)) continue;
    safe[key] = value;
  }
  return safe;
}

export function capture(event: string, properties: Record<string, unknown> = {}): void {
  if (!initialized) return;
  posthog.capture(event, stripForbidden(properties));
}

export function identifyAnonymous(sessionId: string): void {
  if (!initialized) return;
  posthog.identify(sessionId);
}

export function resetAnalytics(): void {
  if (!initialized) return;
  posthog.reset();
}
