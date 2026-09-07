"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge, toneForVerdict } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { deleteIdea, forceSnapshot } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { formatDate } from "@/lib/utils/format";
import { env } from "@/lib/env";
import type { IdeaDetailResponse } from "@/types/api";

interface IdeaHeaderProps {
  idea: IdeaDetailResponse;
  onSnapshotCreated: () => void;
}

export function IdeaHeader({ idea, onSnapshotCreated }: IdeaHeaderProps) {
  const router = useRouter();
  const [rerunStatus, setRerunStatus] = useState<"idle" | "loading" | "error">("idle");
  const [rerunError, setRerunError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [copied, setCopied] = useState(false);

  const shareUrl = `${env.siteUrl}/share/${idea.share_token}`;

  async function handleRerun() {
    setRerunStatus("loading");
    setRerunError(null);
    try {
      await forceSnapshot(idea.idea_id);
      onSnapshotCreated();
      setRerunStatus("idle");
    } catch (err) {
      setRerunError(describeError(err).description);
      setRerunStatus("error");
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteIdea(idea.idea_id);
      router.push("/log");
    } catch {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleCopyShare() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore — link is still visible below
    }
  }

  return (
    <Card elevation="raised">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-display-l text-ink">{idea.keyword || "Untitled idea"}</p>
          <p className="mt-1 text-body text-ink-faint">Tracked since {formatDate(idea.created_at)}</p>
        </div>
        {idea.verdict && idea.raw_score !== null && (
          <Badge tone={toneForVerdict(idea.verdict)} className="text-sm">
            {idea.raw_score}/100 · {idea.verdict}
          </Badge>
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button variant="secondary" size="sm" loading={rerunStatus === "loading"} onClick={handleRerun}>
          Re-run now
        </Button>
        <Button variant="secondary" size="sm" onClick={handleCopyShare}>
          {copied ? "Link copied" : "Copy share link"}
        </Button>
        {!confirmDelete ? (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            className="text-body text-ink-faint hover:text-nogo"
          >
            Delete
          </button>
        ) : (
          <span className="flex items-center gap-2 text-body">
            <span className="text-ink-muted">Delete this log permanently?</span>
            <button type="button" onClick={handleDelete} disabled={deleting} className="text-nogo underline">
              {deleting ? "Deleting..." : "Yes, delete"}
            </button>
            <button type="button" onClick={() => setConfirmDelete(false)} className="text-ink-faint underline">
              Cancel
            </button>
          </span>
        )}
      </div>
      {rerunError && <p className="mt-2 text-body text-nogo">{rerunError}</p>}
    </Card>
  );
}
