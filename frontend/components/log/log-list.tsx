"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useAsync } from "@/lib/hooks/use-async";
import { listIdeas } from "@/lib/api/routes";
import { IdeaCard } from "@/components/log/idea-card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { describeError } from "@/lib/utils/error-message";
import { track } from "@/lib/analytics/events";

export function LogList() {
  const { data: ideas, loading, error, refetch } = useAsync(() => listIdeas(), []);

  useEffect(() => {
    // D1: "returned" is the funnel step that separates this product
    // from a one-shot report — fired once the log actually has
    // something in it, not on every empty-log visit.
    if (ideas && ideas.length > 0) {
      track.returned({ owned_idea_count: ideas.length });
    }
  }, [ideas]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  if (error) {
    const copy = describeError(error);
    return <ErrorState title={copy.title} description={copy.description} onRetry={refetch} />;
  }

  if (!ideas || ideas.length === 0) {
    return (
      <EmptyState
        title="Nothing tracked yet"
        description="A log is a durable record of one idea's score over time — every re-run, every piece of evidence, every kill-criterion you set. Validate a pitch and choose to keep it to start one."
        action={
          <Link href="/">
            <Button>Validate an idea</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {ideas.map((idea) => (
        <IdeaCard key={idea.idea_id} idea={idea} />
      ))}
    </div>
  );
}
