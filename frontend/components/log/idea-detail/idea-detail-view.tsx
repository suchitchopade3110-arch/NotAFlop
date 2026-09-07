"use client";

import { useState } from "react";
import { useAsync } from "@/lib/hooks/use-async";
import { getIdea, getTimeline } from "@/lib/api/routes";
import { IdeaHeader } from "@/components/log/idea-detail/idea-header";
import { DeltaTimeline } from "@/components/log/idea-detail/delta-timeline";
import { CriteriaPanel } from "@/components/log/idea-detail/criteria-panel";
import { EvidencePanel } from "@/components/log/idea-detail/evidence-panel";
import { MilestonesPanel } from "@/components/log/idea-detail/milestones-panel";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { describeError } from "@/lib/utils/error-message";
import { cn } from "@/lib/utils/cn";

const TABS = [
  { id: "timeline", label: "Timeline" },
  { id: "criteria", label: "Kill criteria" },
  { id: "evidence", label: "Evidence & roadmap" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function IdeaDetailView({ ideaId }: { ideaId: string }) {
  const [tab, setTab] = useState<TabId>("timeline");
  const idea = useAsync(() => getIdea(ideaId), [ideaId]);
  const timeline = useAsync(() => getTimeline(ideaId), [ideaId]);

  function refetchAll() {
    idea.refetch();
    timeline.refetch();
  }

  if (idea.loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (idea.error || !idea.data) {
    const copy = describeError(idea.error);
    return <ErrorState title={copy.title} description={copy.description} onRetry={idea.refetch} />;
  }

  return (
    <div className="space-y-6">
      <IdeaHeader idea={idea.data} onSnapshotCreated={refetchAll} />

      <div className="flex gap-1 border-b border-border" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "px-4 py-2.5 text-body font-medium transition-colors",
              tab === t.id ? "border-b-2 border-gold text-ink" : "border-b-2 border-transparent text-ink-faint hover:text-ink-muted",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "timeline" &&
        (timeline.loading ? (
          <Skeleton className="h-64 w-full rounded-2xl" />
        ) : timeline.error ? (
          <ErrorState {...describeError(timeline.error)} onRetry={timeline.refetch} compact />
        ) : (
          <DeltaTimeline entries={timeline.data ?? []} />
        ))}

      {tab === "criteria" && <CriteriaPanel ideaId={ideaId} />}

      {tab === "evidence" && (
        <div className="space-y-8">
          <EvidencePanel ideaId={ideaId} onEvidenceSubmitted={refetchAll} />
          <div>
            <p className="text-label mb-3 text-ink-faint">Roadmap</p>
            <MilestonesPanel ideaId={ideaId} />
          </div>
        </div>
      )}
    </div>
  );
}
