"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { submitEvidence } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { track } from "@/lib/analytics/events";
import type { EvidenceResponse, EvidenceType } from "@/types/api";

const TYPES: { id: EvidenceType; label: string }[] = [
  { id: "interview", label: "Interview" },
  { id: "waitlist", label: "Waitlist" },
  { id: "revenue", label: "Revenue" },
  { id: "letter_of_intent", label: "Letter of intent" },
  { id: "other", label: "Other" },
];

interface EvidenceFormProps {
  ideaId: string;
  onSubmitted: (result: EvidenceResponse) => void;
}

/** C4: submission by type, with the causal link (evidence -> re-score)
 * made legible by the caller once submitEvidence returns — see
 * evidence-panel.tsx's use of the returned snapshot. */
export function EvidenceForm({ ideaId, onSubmitted }: EvidenceFormProps) {
  const [type, setType] = useState<EvidenceType>("interview");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  function setField(key: string, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  function buildPayload(): Record<string, unknown> | null {
    switch (type) {
      case "interview":
        return fields.summary ? { summary: fields.summary, interviewee: fields.interviewee || undefined } : null;
      case "waitlist":
        return fields.count ? { count: Number(fields.count), source: fields.source || undefined } : null;
      case "revenue":
        return fields.amount ? { amount_usd: Number(fields.amount), period: fields.period || undefined } : null;
      case "letter_of_intent":
        return fields.company ? { company: fields.company, summary: fields.summary || undefined } : null;
      default:
        return fields.description ? { description: fields.description } : null;
    }
  }

  const payload = buildPayload();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!payload) return;
    setStatus("loading");
    setError(null);
    try {
      const result = await submitEvidence(ideaId, type, payload);
      setFields({});
      setStatus("idle");
      track.evidenceSubmitted({ type });
      onSubmitted(result);
    } catch (err) {
      setError(describeError(err).description);
      setStatus("error");
    }
  }

  return (
    <Card elevation="flat" as="section">
      <p className="text-heading-sm text-ink">Submit evidence</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {TYPES.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setType(t.id);
              setFields({});
            }}
            className={`rounded-full border px-3 py-1.5 text-body transition-colors ${
              type === t.id ? "border-gold/60 bg-gold/10 text-gold-bright" : "border-border text-ink-muted hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        {type === "interview" && (
          <>
            <Input label="Who did you talk to" placeholder="Role or persona" value={fields.interviewee ?? ""} onChange={(e) => setField("interviewee", e.target.value)} />
            <Textarea label="What did you learn" value={fields.summary ?? ""} onChange={(e) => setField("summary", e.target.value)} rows={3} />
          </>
        )}
        {type === "waitlist" && (
          <>
            <Input label="Signup count" type="number" value={fields.count ?? ""} onChange={(e) => setField("count", e.target.value)} />
            <Input label="Source" placeholder="Landing page, Twitter, etc." value={fields.source ?? ""} onChange={(e) => setField("source", e.target.value)} />
          </>
        )}
        {type === "revenue" && (
          <>
            <Input label="Amount (USD)" type="number" value={fields.amount ?? ""} onChange={(e) => setField("amount", e.target.value)} />
            <Input label="Period" placeholder="First month, MRR, etc." value={fields.period ?? ""} onChange={(e) => setField("period", e.target.value)} />
          </>
        )}
        {type === "letter_of_intent" && (
          <>
            <Input label="Company" value={fields.company ?? ""} onChange={(e) => setField("company", e.target.value)} />
            <Textarea label="Terms" value={fields.summary ?? ""} onChange={(e) => setField("summary", e.target.value)} rows={2} />
          </>
        )}
        {type === "other" && (
          <Textarea label="Describe the evidence" value={fields.description ?? ""} onChange={(e) => setField("description", e.target.value)} rows={3} />
        )}

        {error && <p className="text-body text-nogo">{error}</p>}
        <div className="flex justify-end">
          <Button type="submit" disabled={!payload} loading={status === "loading"}>
            Submit evidence
          </Button>
        </div>
      </form>
    </Card>
  );
}
