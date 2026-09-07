"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { resolveCriterion } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { formatDate } from "@/lib/utils/format";
import type { CriterionResponse } from "@/types/api";

const STATUS_TONE = {
  pending: "neutral",
  met: "go",
  failed: "nogo",
  lapsed: "nogo",
} as const;

export function CriterionRow({ criterion, onResolved }: { criterion: CriterionResponse; onResolved: () => void }) {
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState<"met" | "failed" | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const isPast = new Date(criterion.deadline).getTime() < Date.now();

  async function submitResolution() {
    if (!outcome || note.trim().length < 3) return;
    setStatus("loading");
    setError(null);
    try {
      await resolveCriterion(criterion.criterion_id, outcome, note.trim());
      setResolving(false);
      onResolved();
    } catch (err) {
      setError(describeError(err).description);
      setStatus("error");
    }
  }

  return (
    <Card elevation="flat">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-body text-ink">{criterion.statement}</p>
          <p className="mt-1 text-body text-ink-muted">
            {criterion.metric} · target {criterion.threshold}
          </p>
          <p className="mt-1 text-body text-ink-faint">
            Deadline {formatDate(criterion.deadline)}
            {criterion.status === "pending" && isPast && " · overdue"}
          </p>
          {criterion.resolution_note && (
            <p className="mt-2 text-body text-ink-muted italic">&ldquo;{criterion.resolution_note}&rdquo;</p>
          )}
        </div>
        <Badge tone={STATUS_TONE[criterion.status]}>{criterion.status}</Badge>
      </div>

      {criterion.status === "pending" && (
        <div className="mt-3 border-t border-border-soft pt-3">
          {!resolving ? (
            <Button variant="secondary" size="sm" onClick={() => setResolving(true)}>
              Record outcome
            </Button>
          ) : (
            <div className="space-y-3">
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={outcome === "met" ? "primary" : "secondary"}
                  onClick={() => setOutcome("met")}
                  type="button"
                >
                  Met
                </Button>
                <Button
                  size="sm"
                  variant={outcome === "failed" ? "danger" : "secondary"}
                  onClick={() => setOutcome("failed")}
                  type="button"
                >
                  Failed
                </Button>
              </div>
              <Textarea
                placeholder="What actually happened?"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
              />
              {error && <p className="text-body text-nogo">{error}</p>}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={!outcome || note.trim().length < 3}
                  loading={status === "loading"}
                  onClick={submitResolution}
                >
                  Save outcome
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setResolving(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
