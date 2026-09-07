/** Env-driven config (A1/A3). Every value here is read once, at module
 * load, from NEXT_PUBLIC_* — the only env vars a client bundle can see. */

function readBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

export const env = {
  apiBaseUrl: readBaseUrl(),
  siteUrl: (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/+$/, ""),
  posthogKey: process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "",
  posthogHost: process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com",
  comingSoon: process.env.NEXT_PUBLIC_COMING_SOON === "true",
} as const;
