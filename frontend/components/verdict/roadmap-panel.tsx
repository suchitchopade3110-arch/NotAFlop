"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonLine } from "@/components/ui/skeleton";
import { generatePlan } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import type { PlanResponse } from "@/types/api";

const PRIORITY_TONE = {
  critical: "nogo",
  important: "pivot",
  nice_to_have: "neutral",
} as const;

/** B4: "Go unlocks the roadmap view" — fetched on demand from the
 * existing Phase 5 /plan endpoint rather than pre-loaded, since it's a
 * genuinely separate ask (a 90-day build plan) beyond the free verdict
 * itself, even though nothing about it is paywalled. */
export function RoadmapPanel({ reportId }: { reportId: string }) {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setStatus("loading");
    try {
      const res = await generatePlan(reportId);
      setPlan(res);
      setStatus("idle");
    } catch (err) {
      setError(describeError(err).description);
      setStatus("error");
    }
  }

  if (!plan && status !== "loading") {
    return (
      <Card elevation="glow" className="text-center">
        <p className="text-heading-sm text-ink">Your 90-day roadmap is ready to build</p>
        <p className="mt-1 text-body text-ink-muted">MVP milestones, team gaps, and a revenue model shortlist.</p>
        <div className="mt-4">
          <Button onClick={load}>View roadmap</Button>
        </div>
        {status === "error" && error && <p className="mt-3 text-body text-nogo">{error}</p>}
      </Card>
    );
  }

  if (status === "loading") {
    return (
      <Card elevation="flat" className="space-y-3">
        <SkeletonLine className="h-5 w-40" />
        <SkeletonLine className="h-4 w-full" />
        <SkeletonLine className="h-4 w-5/6" />
      </Card>
    );
  }

  if (!plan) return null;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-label mb-3 text-ink-faint">Build roadmap</p>
        <div className="space-y-3">
          {plan.roadmap.map((block) => (
            <Card key={block.block_title} elevation="flat">
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-heading-sm text-ink">{block.block_title}</p>
                <span className="text-mono text-ink-faint">{block.day_range}</span>
              </div>
              <ul className="mt-2 list-inside list-disc space-y-1">
                {block.tasks.map((task, i) => (
                  <li key={i} className="text-body text-ink-muted">
                    {task}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-body text-ink-faint">Deliverable: {block.deliverable}</p>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <p className="text-label mb-3 text-ink-faint">Team gaps</p>
        <div className="space-y-2">
          {plan.team.map((role) => (
            <div key={role.role} className="flex items-start gap-3">
              <Badge tone={PRIORITY_TONE[role.priority]}>{role.priority.replace("_", " ")}</Badge>
              <div>
                <p className="text-body font-medium text-ink">{role.role}</p>
                <p className="text-body text-ink-muted">{role.reason}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {plan.solo_founder_note && (
        <Card elevation="flat" className="border-gold/30">
          <p className="text-body text-ink-muted">{plan.solo_founder_note}</p>
        </Card>
      )}

      <div>
        <p className="text-label mb-2 text-ink-faint">Revenue model options</p>
        <ul className="flex flex-wrap gap-2">
          {plan.revenue_model_options.map((option) => (
            <li key={option}>
              <Badge tone="gold">{option}</Badge>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
