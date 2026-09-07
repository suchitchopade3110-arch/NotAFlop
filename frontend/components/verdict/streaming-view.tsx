import { DimensionCard } from "@/components/verdict/dimension-card";
import { AggregatePanel } from "@/components/verdict/aggregate-panel";
import { SignalQualityBanner } from "@/components/verdict/signal-quality-banner";
import { ConflictsPanel } from "@/components/verdict/conflicts-panel";
import { DIMENSIONS } from "@/lib/utils/dimensions";
import type { DimensionResult } from "@/lib/hooks/use-validation-flow";
import type { SignalQualityPayload } from "@/types/api";

interface StreamingViewProps {
  dimensions: DimensionResult[];
  signalQuality: SignalQualityPayload | null;
  connecting: boolean;
}

/**
 * B3, the hero visual. A vertical list of dimension cards lights up one
 * at a time as results land (never a spinner-then-dump) while the
 * aggregate panel on the right stays pending until every dimension has
 * resolved. Below md the aggregate panel drops under the dimension list
 * (grid collapses to a single column).
 */
export function StreamingView({ dimensions, signalQuality, connecting }: StreamingViewProps) {
  const landedByKey = new Map(dimensions.map((d) => [d.key, d]));
  const nextPendingIndex = DIMENSIONS.findIndex((d) => !landedByKey.has(d.key));
  const latestLanded = dimensions[dimensions.length - 1];

  return (
    <section className="mx-auto w-full max-w-5xl px-6 py-10 sm:py-14">
      <SignalQualityBanner signalQuality={signalQuality} />

      <div aria-live="polite" className="sr-only">
        {connecting
          ? "Connecting to analysis."
          : latestLanded
            ? `${latestLanded.key.replace(/_/g, " ")} scored ${latestLanded.score} out of 10.`
            : ""}
      </div>

      <div className="grid gap-8 md:grid-cols-[1fr_280px]">
        <div className="space-y-3">
          {connecting && dimensions.length === 0 ? (
            <p className="text-body text-ink-muted">Gathering live market signals before scoring begins...</p>
          ) : null}
          {DIMENSIONS.map((dim, i) => (
            <DimensionCard
              key={dim.key}
              dimensionKey={dim.key}
              result={landedByKey.get(dim.key)}
              active={i === nextPendingIndex}
            />
          ))}
        </div>

        <AggregatePanel
          landedCount={dimensions.length}
          totalCount={DIMENSIONS.length}
          score={null}
          verdict={null}
          signalQuality={signalQuality}
        />
      </div>

      {signalQuality && signalQuality.conflicts.length > 0 && (
        <div className="mt-6">
          <ConflictsPanel conflicts={signalQuality.conflicts} />
        </div>
      )}
    </section>
  );
}
