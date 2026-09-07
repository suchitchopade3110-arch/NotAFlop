"use client";

import { useAsync } from "@/lib/hooks/use-async";
import { listCriteria } from "@/lib/api/routes";
import { CriterionForm } from "@/components/log/idea-detail/criterion-form";
import { CriterionRow } from "@/components/log/idea-detail/criterion-row";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { describeError } from "@/lib/utils/error-message";

export function CriteriaPanel({ ideaId }: { ideaId: string }) {
  const { data: criteria, loading, error, refetch } = useAsync(() => listCriteria(ideaId), [ideaId]);

  return (
    <div className="space-y-4">
      <CriterionForm ideaId={ideaId} onCreated={refetch} />

      {loading && <Skeleton className="h-20 w-full rounded-2xl" />}
      {Boolean(error) && <ErrorState {...describeError(error)} onRetry={refetch} compact />}
      {criteria && criteria.length === 0 && (
        <EmptyState
          title="No commitments yet"
          description="A kill criterion is a falsifiable line in the sand. Set one above."
        />
      )}
      {criteria && criteria.length > 0 && (
        <div className="space-y-3">
          {criteria.map((c) => (
            <CriterionRow key={c.criterion_id} criterion={c} onResolved={refetch} />
          ))}
        </div>
      )}
    </div>
  );
}
