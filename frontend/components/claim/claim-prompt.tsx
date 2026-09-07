"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { claimEmail } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { useSessionStore } from "@/lib/store/session";
import { track } from "@/lib/analytics/events";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * B5: appears only after the verdict has rendered (the caller decides
 * when to mount this), dismissible without penalty, and never
 * reappears in the same browser session once dismissed (claimDismissed
 * in the session store, backed by sessionStorage).
 */
export function ClaimPrompt() {
  const dismissed = useSessionStore((s) => s.claimDismissed);
  const dismiss = useSessionStore((s) => s.dismissClaim);
  const setStoredEmail = useSessionStore((s) => s.setEmail);

  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "sent" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dismissed) track.claimPromptShown();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (dismissed) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!EMAIL_RE.test(email)) {
      setError("That doesn't look like a valid email.");
      return;
    }
    setStatus("loading");
    setError(null);
    track.claimSubmitted();
    try {
      await claimEmail(email);
      setStoredEmail(email);
      setStatus("sent");
    } catch (err) {
      setError(describeError(err).description);
      setStatus("error");
    }
  }

  return (
    <Card elevation="raised" className="mx-auto mb-16 w-full max-w-lg">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-heading-sm text-ink">Want to know when this changes?</p>
          <p className="mt-1 text-body text-ink-muted">
            Get a durable log for this idea — we&apos;ll tell you when the market moves for or
            against it.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            track.claimPromptDismissed();
            dismiss();
          }}
          aria-label="Dismiss"
          className="shrink-0 rounded-md p-1.5 text-ink-faint hover:bg-charcoal hover:text-ink"
        >
          <svg viewBox="0 0 16 16" className="size-4" fill="none" aria-hidden="true">
            <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {status === "sent" ? (
        <p className="mt-4 text-body text-go">
          Check your email for a link. It expires in 15 minutes.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start">
          <div className="flex-1">
            <Input
              type="email"
              placeholder="you@example.com"
              aria-label="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={error}
            />
          </div>
          <Button type="submit" loading={status === "loading"}>
            Send my link
          </Button>
        </form>
      )}
    </Card>
  );
}
