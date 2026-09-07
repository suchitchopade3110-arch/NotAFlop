import { ScoreDial } from "@/components/ui/score-display";
import { toneForVerdict } from "@/components/ui/badge";
import { SkeletonLine } from "@/components/ui/skeleton";

const VERDICT_COPY: Record<string, { word: string; blurb: string }> = {
  go: { word: "Go", blurb: "This idea cleared the bar on live evidence." },
  pivot: { word: "Pivot", blurb: "Not there yet, but the redirect is concrete, not vague." },
  "no-go": { word: "No-Go", blurb: "This idea did not clear the bar as pitched." },
};

const DEFAULT_COPY = VERDICT_COPY["no-go"]!;

interface VerdictHeaderProps {
  score: number;
  verdict: string;
  keyword?: string;
  gateReason: string | null;
  gateReasonLoading: boolean;
}

export function VerdictHeader({ score, verdict, gateReason, gateReasonLoading }: VerdictHeaderProps) {
  const copy = VERDICT_COPY[verdict] ?? DEFAULT_COPY;
  const tone = toneForVerdict(verdict);

  return (
    <div className="flex flex-col items-center gap-6 text-center sm:flex-row sm:items-center sm:gap-10 sm:text-left">
      <ScoreDial score={score} tone={tone} size={140} />
      <div>
        <p className="text-display-l text-ink">{copy.word}</p>
        <p className="mt-2 text-body-l text-ink-muted">{copy.blurb}</p>
        <div className="mt-3 min-h-6">
          {gateReasonLoading ? (
            <SkeletonLine className="h-4 w-64" />
          ) : (
            gateReason && <p className="text-body text-ink-faint">{gateReason}</p>
          )}
        </div>
      </div>
    </div>
  );
}
