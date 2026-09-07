"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { promoteIdea } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { env } from "@/lib/env";
import { track } from "@/lib/analytics/events";

interface ShareCtaProps {
  publicId: string | null;
  size?: "sm" | "md" | "lg";
  variant?: "primary" | "secondary";
  label?: string;
}

/** C5 hook: promotes the just-scored report into a durable idea (so it
 * has a share_token) and hands back a public, unauthenticated link. One
 * promotion per verdict view — the button disables itself once a link
 * exists rather than risking a duplicate idea log on a second click. */
export function ShareCta({ publicId, size = "md", variant = "primary", label = "Get a shareable card" }: ShareCtaProps) {
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    if (!publicId) return;
    setStatus("loading");
    setError(null);
    try {
      const idea = await promoteIdea(publicId);
      const url = `${env.siteUrl}/share/${idea.share_token}`;
      setShareUrl(url);
      setStatus("ready");
      track.ideaPromoted();
    } catch (err) {
      setError(describeError(err).description);
      setStatus("error");
    }
  }

  async function handleCopy() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard blocked — the link is still visible/selectable as text
    }
  }

  if (status === "ready" && shareUrl) {
    return (
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <a
          href={shareUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-mono rounded-lg border border-border bg-charcoal px-3 py-2 text-gold-bright underline-offset-4 hover:underline"
        >
          {shareUrl.replace(/^https?:\/\//, "")}
        </a>
        <Button variant="secondary" size={size} onClick={handleCopy}>
          {copied ? "Copied" : "Copy link"}
        </Button>
      </div>
    );
  }

  return (
    <div>
      <Button variant={variant} size={size} loading={status === "loading"} onClick={handleClick} disabled={!publicId}>
        {label}
      </Button>
      {status === "error" && <p className="mt-2 text-body text-nogo">{error}</p>}
    </div>
  );
}
