import { cn } from "@/lib/utils/cn";

export type BadgeTone = "go" | "pivot" | "nogo" | "gold" | "neutral";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

const toneClasses: Record<BadgeTone, string> = {
  go: "bg-go-wash text-go border-go/30",
  pivot: "bg-pivot-wash text-pivot border-pivot/30",
  nogo: "bg-nogo-wash text-nogo border-nogo/30",
  gold: "bg-gold/10 text-gold-bright border-gold/30",
  neutral: "bg-charcoal-raised text-ink-muted border-border",
};

export function Badge({ className, tone = "neutral", children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-mono text-xs font-medium",
        toneClasses[tone],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

/** Verdict string ("go" | "pivot" | "no-go") -> Badge tone. */
export function toneForVerdict(verdict: string): BadgeTone {
  if (verdict === "go") return "go";
  if (verdict === "pivot") return "pivot";
  return "nogo";
}
