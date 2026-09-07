"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { EvidenceForm } from "@/components/log/idea-detail/evidence-form";
import type { EvidenceResponse } from "@/types/api";

interface EvidencePanelProps {
  ideaId: string;
  onEvidenceSubmitted: () => void; // refetch idea + timeline
}

/** C4: "Make the causal link legible — evidence submitted, score
 * re-run, this is what moved." Rendered as its own callout right after
 * submission rather than leaving the founder to notice the change in
 * the timeline later. */
export function EvidencePanel({ ideaId, onEvidenceSubmitted }: EvidencePanelProps) {
  const [justSubmitted, setJustSubmitted] = useState<EvidenceResponse | null>(null);

  function handleSubmitted(result: EvidenceResponse) {
    setJustSubmitted(result);
    onEvidenceSubmitted();
  }

  return (
    <div className="space-y-4">
      {justSubmitted && (
        <Card elevation="glow">
          <p className="text-body font-medium text-ink">Evidence recorded.</p>
          {justSubmitted.snapshot ? (
            <p className="mt-1 text-body text-ink-muted">
              That triggered a re-score: your idea is now at{" "}
              <span className="text-mono text-gold-bright">{justSubmitted.snapshot.raw_score}</span> (
              {justSubmitted.snapshot.verdict}). See the timeline below for what moved.
            </p>
          ) : (
            <p className="mt-1 text-body text-ink-muted">
              This evidence type doesn&apos;t trigger an automatic re-score on its own. It&apos;s saved
              to your idea&apos;s history.
            </p>
          )}
        </Card>
      )}
      <EvidenceForm ideaId={ideaId} onSubmitted={handleSubmitted} />
    </div>
  );
}
