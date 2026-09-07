/**
 * Client-side heuristic keyword extraction — a stand-in for a real
 * extraction step that the backend does not expose to callers.
 *
 * PHASE 4 GAP (see task report): POST /api/phase2/validate requires a
 * `keyword` up front to search the live data sources, but the only
 * keyword extractor on the backend (services/keyword_extractor.py) is
 * called internally by POST /api/phase3/analyze itself, as a fallback
 * for when `keyword` is omitted from that request — there is no
 * standalone endpoint the frontend can call between Phase 1 (filter)
 * and Phase 2 (validate/gather signals) to get a real extracted
 * keyword. Per the "no backend changes" constraint, this file works
 * around that gap with a crude local heuristic used ONLY to seed the
 * signal-gathering call; the actual keyword persisted on the report is
 * still the backend's own LLM extraction (this app omits `keyword` from
 * the analyze request so the backend re-derives it authoritatively).
 * The real fix is a callable extraction step (or letting
 * /api/phase2/validate accept a transcript itself) — flagged for a
 * future phase, not patched here.
 */

const STOPWORDS = new Set([
  "a", "an", "the", "and", "or", "but", "so", "for", "nor", "yet",
  "i", "we", "you", "they", "he", "she", "it", "this", "that", "these", "those",
  "is", "are", "was", "were", "be", "been", "being", "am",
  "to", "of", "in", "on", "at", "by", "with", "from", "as", "into", "onto",
  "want", "wants", "wanted", "building", "build", "built", "make", "makes", "making",
  "app", "startup", "idea", "product", "platform", "company", "our", "my", "your",
  "will", "would", "can", "could", "should", "have", "has", "had", "do", "does",
  "just", "really", "very", "like", "basically", "essentially",
]);

/** Picks the 2-5 most meaningful words from a transcript, in the order
 * they first appear, for use as a market-signal search phrase. */
export function heuristicKeyword(transcript: string): string {
  const words = transcript
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOPWORDS.has(w));

  const seen = new Set<string>();
  const picked: string[] = [];
  for (const word of words) {
    if (seen.has(word)) continue;
    seen.add(word);
    picked.push(word);
    if (picked.length >= 4) break;
  }

  if (picked.length === 0) return "startup idea";
  return picked.join(" ");
}
