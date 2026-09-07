"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { verifyClaimToken } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { useSessionStore } from "@/lib/store/session";
import { track } from "@/lib/analytics/events";

export function ClaimVerify() {
  const token = useSearchParams().get("token");
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const setEmail = useSessionStore((s) => s.setEmail);
  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [claimedIdeas, setClaimedIdeas] = useState(0);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("This link is missing its token.");
      return;
    }
    verifyClaimToken(token)
      .then((res) => {
        setSessionId(res.session_id);
        setEmail(res.email);
        setClaimedIdeas(res.claimed_ideas);
        setStatus("done");
        track.claimed();
      })
      .catch((err) => {
        setError(describeError(err).description);
        setStatus("error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <section className="mx-auto flex w-full max-w-md flex-1 items-center px-6 py-16">
      <Card elevation="raised" className="w-full text-center">
        {status === "loading" && <p className="text-body text-ink-muted">Verifying your link...</p>}

        {status === "done" && (
          <>
            <p className="text-heading-sm text-ink">You&apos;re in</p>
            <p className="mt-2 text-body text-ink-muted">
              {claimedIdeas > 0
                ? `${claimedIdeas} idea${claimedIdeas > 1 ? "s" : ""} from this browser ${claimedIdeas > 1 ? "are" : "is"} now saved to your log.`
                : "Your log is ready. Validate an idea to start tracking it."}
            </p>
            <Link href="/log" className="mt-5 inline-block">
              <Button>Go to your log</Button>
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <p className="text-heading-sm text-ink">This link didn&apos;t work</p>
            <p className="mt-2 text-body text-ink-muted">{error}</p>
            <p className="mt-1 text-body text-ink-faint">Magic links expire after 15 minutes and can only be used once.</p>
            <Link href="/" className="mt-5 inline-block">
              <Button variant="secondary">Back to NotAFlop</Button>
            </Link>
          </>
        )}
      </Card>
    </section>
  );
}
