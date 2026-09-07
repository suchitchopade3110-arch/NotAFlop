"use client";

import { useEffect } from "react";
import { useSessionStore } from "@/lib/store/session";
import { mintSession } from "@/lib/api/routes";

/**
 * Mints the anonymous session on first load (A3, constraint #2 —
 * anonymous, no account wall). Mounted once in the root layout. If a
 * session id is already in localStorage, apiFetch already attaches it
 * to every request and the backend just echoes it back — this only
 * needs to run the POST once to obtain a fresh one when there is none.
 */
export function SessionBootstrap() {
  useEffect(() => {
    const store = useSessionStore.getState();
    store.hydrate();

    if (!useSessionStore.getState().sessionId) {
      mintSession()
        .then((res) => useSessionStore.getState().setSessionId(res.session_id))
        .catch(() => {
          // Offline on first load — apiFetch will mint one on the next
          // successful request instead (the backend sets X-Session-Id
          // on every response, captured by client.ts automatically).
        });
    }
  }, []);

  return null;
}
