import { Card } from "@/components/ui/card";
import { ShareCta } from "@/components/verdict/share-cta";
import type { RiskItem } from "@/types/api";
import { dimensionLabel } from "@/lib/utils/dimensions";

/** Pivot surfaces concrete redirection (B4) — the specific dimensions
 * holding the idea back, framed as what to rework, not a vague "close
 * but not quite." */
export function PivotVerdict({ publicId, topRisks }: { publicId: string | null; topRisks: RiskItem[] }) {
  return (
    <div className="space-y-6">
      <Card elevation="raised" className="border-pivot/30">
        <p className="text-label text-pivot">Where to redirect</p>
        <ul className="mt-4 space-y-4">
          {topRisks.map((risk) => (
            <li key={risk.agent} className="border-l-2 border-pivot/50 pl-4">
              <p className="text-body font-medium text-ink">{dimensionLabel(risk.agent)}</p>
              <p className="text-body text-ink-muted">{risk.feedback}</p>
            </li>
          ))}
        </ul>
      </Card>
      <div className="flex justify-end">
        <ShareCta publicId={publicId} variant="secondary" size="sm" label="Share this verdict" />
      </div>
    </div>
  );
}
