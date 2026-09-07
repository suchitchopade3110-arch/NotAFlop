"use client";

import { useState } from "react";
import { LogoMark } from "@/components/layout/logo-mark";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { claimEmail } from "@/lib/api/routes";
import { track } from "@/lib/analytics/events";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * D6: live before launch day. One promise, one field.
 *
 * PHASE 4 GAP: there's no dedicated waitlist/signup-capture endpoint on
 * the backend — the only email-collecting route is POST /v1/auth/claim,
 * which issues a short-TTL (15 min) magic link rather than durably
 * storing the address; nothing is written to the `accounts` collection
 * until that link is actually clicked. This form calls it anyway as the
 * closest available capability (no backend change per constraint #1),
 * which still leaves a server-side trace (magic_link_issued log line)
 * even though most pre-launch signups won't click through in time. The
 * real fix is a dedicated durable capture endpoint.
 */
export function ComingSoonPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!EMAIL_RE.test(email)) {
      setError("That doesn't look like a valid email.");
      return;
    }
    setStatus("loading");
    setError(null);
    try {
      await claimEmail(email);
      setStatus("done");
      track.comingSoonSignup();
    } catch {
      setError("Something went wrong. Try again in a moment.");
      setStatus("error");
    }
  }

  return (
    <main id="main-content" className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <LogoMark className="mb-10" />
      <h1 className="text-display-xl text-ink">
        Know if it&apos;s worth building<span className="text-gold-bright">.</span>
      </h1>
      <p className="mt-5 max-w-md text-body-l text-ink-muted">
        A free, evidence-grounded verdict on your startup idea. Coming soon.
      </p>

      {status === "done" ? (
        <p className="mt-8 text-body text-go">You&apos;re on the list. We&apos;ll email you at launch.</p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-8 flex w-full max-w-sm flex-col gap-3 sm:flex-row">
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
            Notify me
          </Button>
        </form>
      )}

      <p className="mt-6 text-body text-ink-faint">Free forever. No spam, one email at launch.</p>
    </main>
  );
}
