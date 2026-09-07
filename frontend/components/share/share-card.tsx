import Link from "next/link";
import { ScoreDial } from "@/components/ui/score-display";
import { toneForVerdict } from "@/components/ui/badge";
import { benchmarkFor } from "@/lib/utils/benchmarks";
import { formatDate } from "@/lib/utils/format";
import type { ShareCardResponse } from "@/types/api";

const VERDICT_WORD: Record<string, string> = { go: "Go", pivot: "Pivot", "no-go": "No-Go" };

/**
 * C5: one vertical, mobile-first card — score, verdict, headline
 * reasons, and (for a rejection) a benchmark against a known startup
 * failure. Never raw pitch text, email, or evidence — this component
 * only ever receives ShareCardResponse, which structurally can't carry
 * any of those (see services/share.py on the backend).
 */
export function ShareCard({ card }: { card: ShareCardResponse }) {
  const tone = toneForVerdict(card.verdict);
  const benchmark = card.verdict === "no-go" ? benchmarkFor(card.keyword, card.keyword + card.created_at) : null;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-5 py-10">
      <div className="w-full max-w-sm rounded-3xl border border-gold/25 bg-charcoal-raised p-7 shadow-nf-gold sm:p-9">
        <p className="text-label text-center text-ink-faint">NotAFlop verdict</p>

        <div className="mt-5 flex justify-center">
          <ScoreDial score={card.raw_score} tone={tone} size={148} label={VERDICT_WORD[card.verdict] ?? card.verdict} />
        </div>

        <p className="mt-5 text-center text-heading text-ink">{card.keyword || "This idea"}</p>

        {card.top_reasons.length > 0 && (
          <ul className="mt-5 space-y-2 border-t border-border-soft pt-5">
            {card.top_reasons.map((reason) => (
              <li key={reason} className="text-body text-ink-muted">
                {reason}
              </li>
            ))}
          </ul>
        )}

        {benchmark && (
          <div className="mt-5 rounded-xl border border-border-soft bg-obsidian/60 px-4 py-3">
            <p className="text-body text-ink-muted">
              Reminds us of <span className="text-ink">{benchmark.name}</span> ({benchmark.year}) — it{" "}
              {benchmark.lesson}
            </p>
          </div>
        )}

        <p className="mt-6 text-center text-body text-ink-faint">Scored {formatDate(card.created_at)}</p>
      </div>

      <Link
        href="/"
        className="mt-6 text-body text-gold-bright underline-offset-4 hover:underline"
      >
        Validate your own idea — free
      </Link>
    </div>
  );
}
