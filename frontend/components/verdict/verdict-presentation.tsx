import { VerdictHeader } from "@/components/verdict/verdict-header";
import { GoVerdict } from "@/components/verdict/go-verdict";
import { PivotVerdict } from "@/components/verdict/pivot-verdict";
import { NoGoVerdict } from "@/components/verdict/nogo-verdict";
import { DimensionCard } from "@/components/verdict/dimension-card";
import { SignalQualityBanner } from "@/components/verdict/signal-quality-banner";
import { ConflictsPanel } from "@/components/verdict/conflicts-panel";
import { orderDimensionKeys } from "@/lib/utils/dimensions";
import { useGateReason } from "@/lib/hooks/use-gate-reason";
import type { VerdictData } from "@/lib/hooks/use-validation-flow";

interface VerdictPresentationProps {
  verdict: VerdictData;
}

/** B4: three distinct treatments dispatched by verdict string, sharing
 * one header + one full dimension breakdown at the bottom so a founder
 * can always see the whole picture regardless of which treatment they
 * landed on. */
export function VerdictPresentation({ verdict }: VerdictPresentationProps) {
  const { gateReason, topRisks, loading } = useGateReason(verdict.dimensions);
  const orderedKeys = orderDimensionKeys(verdict.dimensions.map((d) => d.key));
  const byKey = new Map(verdict.dimensions.map((d) => [d.key, d]));

  return (
    <section className="mx-auto w-full max-w-3xl px-6 py-10 sm:py-14">
      {verdict.recovered && (
        <p className="mb-6 rounded-lg border border-border bg-charcoal px-4 py-2 text-body text-ink-faint">
          Reconnected after a dropped connection — this verdict finished on our servers.
        </p>
      )}

      <SignalQualityBanner signalQuality={verdict.signalQuality} />

      <VerdictHeader
        score={verdict.score}
        verdict={verdict.verdict}
        gateReason={gateReason}
        gateReasonLoading={loading}
      />

      <div className="mt-10">
        {verdict.verdict === "go" && <GoVerdict publicId={verdict.publicId} />}
        {verdict.verdict === "pivot" && <PivotVerdict publicId={verdict.publicId} topRisks={topRisks} />}
        {verdict.verdict === "no-go" && <NoGoVerdict publicId={verdict.publicId} topRisks={topRisks} />}
      </div>

      {verdict.signalQuality && verdict.signalQuality.conflicts.length > 0 && (
        <div className="mt-6">
          <ConflictsPanel conflicts={verdict.signalQuality.conflicts} />
        </div>
      )}

      <div className="mt-12">
        <p className="text-label mb-3 text-ink-faint">Full breakdown</p>
        <div className="space-y-3">
          {orderedKeys.map((key) => (
            <DimensionCard key={key} dimensionKey={key} result={byKey.get(key)} />
          ))}
        </div>
      </div>

      {verdict.errors.length > 0 && (
        <p className="mt-6 text-body text-ink-faint">
          Note: {verdict.errors.length} dimension{verdict.errors.length > 1 ? "s" : ""} could not be scored and
          were excluded rather than counted as a zero.
        </p>
      )}
    </section>
  );
}
