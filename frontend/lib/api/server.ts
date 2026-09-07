import { env } from "@/lib/env";
import type { ShareCardResponse } from "@/types/api";

/** Server-side fetch for the one route that's genuinely public and
 * unauthenticated (C5) — no X-Session-Id, no browser localStorage
 * available in a server component anyway. Kept separate from
 * lib/api/client.ts on purpose: that client is browser-only (reads the
 * session store), this one isn't. */
export async function fetchShareCard(token: string): Promise<ShareCardResponse | null> {
  const res = await fetch(`${env.apiBaseUrl}/v1/share/${token}`, {
    // A share card can be re-scored after publishing (evidence, a
    // scheduled snapshot) — never serve a stale verdict from cache.
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as ShareCardResponse;
}
