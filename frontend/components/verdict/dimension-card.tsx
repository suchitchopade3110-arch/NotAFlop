import { Card } from "@/components/ui/card";
import { DimensionScore } from "@/components/ui/score-display";
import { Skeleton } from "@/components/ui/skeleton";
import { dimensionDescription, dimensionLabel } from "@/lib/utils/dimensions";
import type { DimensionResult } from "@/lib/hooks/use-validation-flow";

interface DimensionCardProps {
  dimensionKey: string;
  result?: DimensionResult;
  active?: boolean;
}

export function DimensionCard({ dimensionKey, result, active }: DimensionCardProps) {
  const label = dimensionLabel(dimensionKey);
  const landed = !!result;

  return (
    <Card
      elevation={active && !landed ? "glow" : "flat"}
      className="transition-[border-color,box-shadow] duration-300"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-heading-sm text-ink">{label}</p>
          <p className="mt-0.5 text-body text-ink-faint">{dimensionDescription(dimensionKey)}</p>
        </div>
        {landed ? (
          <DimensionScore score={result.score} className="shrink-0" />
        ) : (
          <span className="text-mono shrink-0 text-ink-faint" aria-hidden="true">
            {active ? "···" : "—"}
          </span>
        )}
      </div>

      {landed ? (
        <div className="mt-3 border-t border-border-soft pt-3">
          <p className="text-body text-ink">{result.feedback}</p>
          {result.evidence && <p className="mt-1.5 text-body text-ink-muted italic">&ldquo;{result.evidence}&rdquo;</p>}
        </div>
      ) : (
        active && (
          <div className="mt-3 space-y-2 border-t border-border-soft pt-3" aria-hidden="true">
            <Skeleton className="h-3.5 w-4/5" />
            <Skeleton className="h-3.5 w-3/5" />
          </div>
        )
      )}
    </Card>
  );
}
