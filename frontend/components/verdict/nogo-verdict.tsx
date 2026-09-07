import { Card } from "@/components/ui/card";
import { ShareCta } from "@/components/verdict/share-cta";
import type { RiskItem } from "@/types/api";
import { dimensionLabel } from "@/lib/utils/dimensions";

/**
 * No-Go gets the most design attention (B4) — the majority verdict and
 * the one most likely to be shared. Rendered as a checklist of "what
 * would need to be true," a task to work through, never a scoreboard
 * or a dead end.
 */
export function NoGoVerdict({ publicId, topRisks }: { publicId: string | null; topRisks: RiskItem[] }) {
  return (
    <div className="space-y-6">
      <Card elevation="raised" className="border-nogo/30 bg-gradient-to-b from-nogo-wash to-transparent">
        <p className="text-label text-nogo">What would need to be true</p>
        <ul className="mt-4 space-y-4">
          {topRisks.map((risk) => (
            <li key={risk.agent} className="flex gap-3">
              <span
                className="mt-1 flex size-5 shrink-0 items-center justify-center rounded border border-nogo/50 text-nogo"
                aria-hidden="true"
              >
                <svg viewBox="0 0 12 12" className="size-3" fill="none">
                  <path d="M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </span>
              <div>
                <p className="text-body font-medium text-ink">{dimensionLabel(risk.agent)}</p>
                <p className="text-body text-ink-muted">{risk.feedback}</p>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card elevation="glow" className="flex flex-col items-center gap-3 text-center">
        <p className="text-heading-sm text-ink">This is worth putting somewhere</p>
        <p className="max-w-sm text-body text-ink-muted">
          A No-Go against a specific pitch, benchmarked against a known startup failure: a real
          artifact, not a dead end.
        </p>
        <ShareCta publicId={publicId} size="lg" label="Get my shareable card" />
      </Card>
    </div>
  );
}
