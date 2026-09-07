import { cn } from "@/lib/utils/cn";

type Elevation = "flat" | "raised" | "glow";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevation?: Elevation;
  as?: "div" | "section" | "article";
}

const elevationClasses: Record<Elevation, string> = {
  flat: "bg-charcoal border border-border",
  raised: "bg-charcoal-raised border border-border shadow-nf-md",
  glow: "bg-charcoal-raised border border-gold/40 shadow-nf-gold",
};

export function Card({ className, elevation = "flat", as: Tag = "div", ...props }: CardProps) {
  return (
    <Tag className={cn("rounded-2xl p-6", elevationClasses[elevation], className)} {...props} />
  );
}
