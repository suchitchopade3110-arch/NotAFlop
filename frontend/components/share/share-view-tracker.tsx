"use client";

import { useEffect } from "react";
import { track } from "@/lib/analytics/events";

/** The share page (app/share/[token]/page.tsx) is a server component —
 * this tiny client leaf is only here to fire the D1 funnel event, since
 * PostHog only runs in the browser. */
export function ShareViewTracker({ verdict }: { verdict: string }) {
  useEffect(() => {
    track.shareCardViewed({ verdict });
  }, [verdict]);

  return null;
}
