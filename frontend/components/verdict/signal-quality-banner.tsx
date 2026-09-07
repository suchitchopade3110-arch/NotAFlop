import type { SignalQualityPayload } from "@/types/api";

/** B3: "low_confidence surfaced prominently... this is a trust feature.
 * Do not bury it." — full-width banner above the fold, not a small icon
 * tucked into a corner of the score panel. */
export function SignalQualityBanner({ signalQuality }: { signalQuality: SignalQualityPayload | null }) {
  if (!signalQuality) return null;

  if (!signalQuality.low_confidence) {
    return (
      <div className="mb-6 flex items-center gap-3 rounded-xl border border-go/25 bg-go-wash px-5 py-3">
        <span className="text-mono text-go" aria-hidden="true">
          ●
        </span>
        <p className="text-body text-ink">
          Backed by live data from multiple sources — signal quality{" "}
          <span className="text-mono text-ink">{Math.round(signalQuality.signal_quality * 100)}%</span>.
        </p>
      </div>
    );
  }

  return (
    <div role="status" className="mb-6 flex items-start gap-3 rounded-xl border border-pivot/30 bg-pivot-wash px-5 py-4">
      <span className="mt-0.5 text-mono text-pivot" aria-hidden="true">
        ▲
      </span>
      <div>
        <p className="text-body font-medium text-ink">Low confidence — fewer than two live sources came back</p>
        <p className="mt-1 text-body text-ink-muted">
          This verdict is grounded in less live market evidence than usual. Treat the score as a
          starting point, not the final word, until more signal is available.
        </p>
      </div>
    </div>
  );
}
