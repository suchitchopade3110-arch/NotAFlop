import { cn } from "@/lib/utils/cn";
import type { BadgeTone } from "@/components/ui/badge";

const toneColor: Record<BadgeTone, string> = {
  go: "var(--color-go)",
  pivot: "var(--color-pivot)",
  nogo: "var(--color-nogo)",
  gold: "var(--color-gold-bright)",
  neutral: "var(--color-ink-muted)",
};

interface ScoreDialProps {
  score: number; // 0-100
  tone: BadgeTone;
  size?: number;
  label?: string;
  pending?: boolean;
}

/** Circular score dial — the aggregate score in the streaming view (B3)
 * and the share card (C5). Resolves from empty to a colored arc; while
 * `pending` it renders an unfilled ring with a mono placeholder. */
export function ScoreDial({ score, tone, size = 168, label, pending }: ScoreDialProps) {
  const stroke = size * 0.07;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, score));
  const offset = circumference * (1 - clamped / 100);
  const color = pending ? "var(--color-border)" : toneColor[tone];

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={label ?? `Score ${score} of 100`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-border-soft)"
          strokeWidth={stroke}
        />
        {!pending && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 700ms ease-out" }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {pending ? (
          <span className="text-mono text-ink-faint">···</span>
        ) : (
          <span className="text-display-l text-ink" style={{ fontVariantNumeric: "tabular-nums" }}>
            {clamped}
          </span>
        )}
        {label && !pending && <span className="text-label mt-1 text-ink-faint">{label}</span>}
      </div>
    </div>
  );
}

interface DimensionScoreProps {
  score: number; // 0-10
  className?: string;
}

/** Small inline score chip for a single dimension card — /10, mono. */
export function DimensionScore({ score, className }: DimensionScoreProps) {
  const tone = score >= 7 ? "text-go" : score >= 4 ? "text-pivot" : "text-nogo";
  return (
    <span className={cn("text-mono font-semibold", tone, className)} style={{ fontVariantNumeric: "tabular-nums" }}>
      {score}
      <span className="text-ink-faint">/10</span>
    </span>
  );
}
