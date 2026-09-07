"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { AgentResult, FilterResponse } from "@/types/api";

const MAX_LENGTH = 5000;

function CheckRow({ label, result }: { label: string; result: AgentResult }) {
  return (
    <div className="flex items-start gap-3 border-t border-border-soft py-3 first:border-t-0 first:pt-0">
      <span
        className={result.passed ? "text-go" : "text-nogo"}
        aria-hidden="true"
      >
        {result.passed ? "✓" : "✕"}
      </span>
      <div>
        <p className="text-body font-medium text-ink">{label}</p>
        <p className="mt-0.5 text-body text-ink-muted">{result.feedback}</p>
      </div>
    </div>
  );
}

interface FilterFeedbackProps {
  transcript: string;
  filterResult: FilterResponse;
  onRevise: (revisedText: string) => void;
}

/** B2's filter-gate handling — the founder edits in place rather than
 * starting over, with the two structured signals that failed named
 * explicitly rather than folded into one vague rejection. */
export function FilterFeedback({ transcript, filterResult, onRevise }: FilterFeedbackProps) {
  const [draft, setDraft] = useState(transcript);
  const overLimit = draft.length > MAX_LENGTH;

  return (
    <Card elevation="raised" className="w-full">
      <p className="text-heading-sm text-ink">This pitch needs another pass before we can score it</p>
      <p className="mt-1 text-body text-ink-muted">
        Two quick checks run before the full analysis. Here is what came back.
      </p>

      <div className="mt-4">
        <CheckRow label="Is the problem narrow enough to test?" result={filterResult.narrow_problem} />
        <CheckRow label="Is the pitch clear enough to score?" result={filterResult.pitch_clarity} />
      </div>

      <label htmlFor="pitch-revision" className="text-label mb-2 mt-6 block text-ink-muted">
        Revise your pitch
      </label>
      <Textarea
        id="pitch-revision"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={7}
        maxLength={MAX_LENGTH}
        showCount
        error={overLimit ? `Keep it under ${MAX_LENGTH.toLocaleString()} characters.` : null}
      />

      <div className="mt-4 flex justify-end">
        <Button
          type="button"
          disabled={draft.trim().length < 20 || overLimit}
          onClick={() => onRevise(draft.trim())}
        >
          Re-run the check
        </Button>
      </div>
    </Card>
  );
}
