import { Card } from "@/components/ui/card";
import { ScoreDial } from "@/components/ui/score-display";
import { sourceLabel } from "@/lib/utils/sources";
import { toneForVerdict } from "@/components/ui/badge";
import type { SignalQualityPayload } from "@/types/api";

interface AggregatePanelProps {
  landedCount: number;
  totalCount: number;
  score: number | null;
  verdict: string | null;
  signalQuality: SignalQualityPayload | null;
}

/** B3: "the aggregate score resolves last, after the dimensions that
 * produce it" — this panel stays visibly pending (empty dial, no
 * verdict word) until the caller passes a resolved score/verdict. */
export function AggregatePanel({ landedCount, totalCount, score, verdict, signalQuality }: AggregatePanelProps) {
  const resolved = score !== null && verdict !== null;

  return (
    <div className="space-y-4 md:sticky md:top-6">
      <Card elevation={resolved ? "glow" : "flat"} className="flex flex-col items-center text-center">
        <p className="text-label text-ink-faint">
          {resolved ? "Verdict" : `Scoring ${landedCount} of ${totalCount}`}
        </p>
        <div className="mt-3">
          <ScoreDial score={score ?? 0} tone={resolved ? toneForVerdict(verdict!) : "neutral"} pending={!resolved} />
        </div>
        {!resolved && (
          <p className="mt-2 text-body text-ink-faint" aria-live="polite">
            Waiting on the remaining dimensions before the score locks in.
          </p>
        )}
      </Card>

      {signalQuality && (
        <Card elevation="flat">
          <p className="text-label text-ink-faint">Live signal coverage</p>
          <ul className="mt-3 space-y-2">
            {Object.entries(signalQuality.signal_quality_by_source).map(([source, quality]) => (
              <li key={source} className="flex items-center justify-between gap-3">
                <span className="text-body text-ink-muted">{sourceLabel(source)}</span>
                <span className="h-1.5 w-16 overflow-hidden rounded-full bg-border-soft" aria-hidden="true">
                  <span
                    className="block h-full rounded-full bg-gold"
                    style={{ width: `${Math.round(quality * 100)}%` }}
                  />
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
