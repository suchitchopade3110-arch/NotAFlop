"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { createCriterion } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { track } from "@/lib/analytics/events";

function tomorrowIso(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 16);
}

/** C3: "The form should make a vague commitment hard to write." The
 * backend only rejects near-empty strings (<3 chars) — everything past
 * that is the UI's job: concrete placeholders, a specificity nudge, and
 * a deadline field that defaults forward, never blank. */
export function CriterionForm({ ideaId, onCreated }: { ideaId: string; onCreated: () => void }) {
  const [statement, setStatement] = useState("");
  const [metric, setMetric] = useState("");
  const [threshold, setThreshold] = useState("");
  const [deadline, setDeadline] = useState(tomorrowIso());
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const statementTooVague = statement.trim().length > 0 && statement.trim().length < 15;
  const canSubmit = statement.trim().length >= 15 && metric.trim().length >= 3 && threshold.trim().length >= 2 && !!deadline;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setStatus("loading");
    setError(null);
    try {
      await createCriterion(ideaId, {
        statement: statement.trim(),
        metric: metric.trim(),
        threshold: threshold.trim(),
        deadline: new Date(deadline).toISOString(),
      });
      setStatement("");
      setMetric("");
      setThreshold("");
      setDeadline(tomorrowIso());
      setStatus("idle");
      track.criterionCreated();
      onCreated();
    } catch (err) {
      setError(describeError(err).description);
      setStatus("error");
    }
  }

  return (
    <Card elevation="flat" as="section">
      <p className="text-heading-sm text-ink">Set a kill criterion</p>
      <p className="mt-1 text-body text-ink-muted">
        Write the exact result that would prove this idea wrong — a statement that could actually
        fail, not a hope.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <Textarea
          label="What would need to happen for this idea to be dead"
          placeholder="If fewer than 20 of the first 100 people I show this to say they'd pay for it, this idea is dead."
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          rows={3}
          hint={statementTooVague ? "A bit more specificity — name the number and the group." : undefined}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Metric"
            placeholder="Waitlist conversion rate"
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
          />
          <Input
            label="Threshold"
            placeholder="20 of 100, or 10%"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          />
        </div>
        <Input
          label="Deadline"
          type="datetime-local"
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
        />
        {error && <p className="text-body text-nogo">{error}</p>}
        <div className="flex justify-end">
          <Button type="submit" disabled={!canSubmit} loading={status === "loading"}>
            Commit to this test
          </Button>
        </div>
      </form>
    </Card>
  );
}
