import Link from "next/link";
import { cn } from "@/lib/utils/cn";

export function LogoMark({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("inline-flex items-center gap-2", className)} aria-label="NotAFlop home">
      <span
        aria-hidden="true"
        className="flex size-8 items-center justify-center rounded-lg border border-gold/40 bg-gradient-to-br from-gold-bright/20 to-transparent text-mono text-gold-bright"
      >
        N
      </span>
      <span className="text-heading-sm text-ink">NotAFlop</span>
    </Link>
  );
}
