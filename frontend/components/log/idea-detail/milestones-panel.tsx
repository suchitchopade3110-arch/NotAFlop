"use client";

import { useState } from "react";
import { useAsync } from "@/lib/hooks/use-async";
import { listMilestones, patchMilestone } from "@/lib/api/routes";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { describeError } from "@/lib/utils/error-message";
import { cn } from "@/lib/utils/cn";

export function MilestonesPanel({ ideaId }: { ideaId: string }) {
  const { data: milestones, loading, error, refetch } = useAsync(() => listMilestones(ideaId), [ideaId]);
  const [toggling, setToggling] = useState<string | null>(null);

  async function toggle(milestoneId: string, completed: boolean) {
    setToggling(milestoneId);
    try {
      await patchMilestone(milestoneId, completed);
      refetch();
    } finally {
      setToggling(null);
    }
  }

  if (loading) return <Skeleton className="h-32 w-full rounded-2xl" />;
  if (error) return <ErrorState {...describeError(error)} onRetry={refetch} compact />;
  if (!milestones || milestones.length === 0) {
    return (
      <EmptyState
        title="No roadmap yet"
        description="A build roadmap appears here once your idea has a Go or Pivot verdict with a 90-day plan generated."
      />
    );
  }

  const completedCount = milestones.filter((m) => m.completed).length;

  return (
    <div className="space-y-3">
      <p className="text-body text-ink-faint">
        {completedCount} of {milestones.length} complete
      </p>
      {milestones.map((m) => (
        <Card key={m.milestone_id} elevation="flat" className={cn(m.completed && "opacity-70")}>
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={m.completed}
              disabled={toggling === m.milestone_id}
              onChange={(e) => toggle(m.milestone_id, e.target.checked)}
              className="mt-1 size-4 shrink-0 accent-gold"
            />
            <div>
              <p className={cn("text-body font-medium text-ink", m.completed && "line-through")}>
                {m.block_title}
              </p>
              <p className="text-body text-ink-faint">{m.day_range}</p>
              <p className="mt-1 text-body text-ink-muted">{m.deliverable}</p>
            </div>
          </label>
        </Card>
      ))}
    </div>
  );
}
