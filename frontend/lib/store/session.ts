import { create } from "zustand";

const SESSION_KEY = "notaflop.session_id";
const CLAIMED_KEY = "notaflop.claimed_email";
const CLAIM_DISMISSED_KEY = "notaflop.claim_dismissed"; // sessionStorage — per browser tab session

function readLocal(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private-mode / storage-blocked browsers — the app still works,
    // just re-mints a session next load instead of persisting one.
  }
}

interface SessionState {
  sessionId: string | null;
  email: string | null;
  hydrated: boolean;
  claimDismissed: boolean;
  setSessionId: (id: string) => void;
  setEmail: (email: string) => void;
  dismissClaim: () => void;
  hydrate: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  email: null,
  hydrated: false,
  claimDismissed: false,
  setSessionId: (id: string) => {
    writeLocal(SESSION_KEY, id);
    set({ sessionId: id });
  },
  setEmail: (email: string) => {
    writeLocal(CLAIMED_KEY, email);
    set({ email });
  },
  dismissClaim: () => {
    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.setItem(CLAIM_DISMISSED_KEY, "1");
      } catch {
        // ignore — worst case the prompt can reappear this tab session
      }
    }
    set({ claimDismissed: true });
  },
  hydrate: () => {
    if (get().hydrated) return;
    const sessionId = readLocal(SESSION_KEY);
    const email = readLocal(CLAIMED_KEY);
    let claimDismissed = false;
    if (typeof window !== "undefined") {
      try {
        claimDismissed = window.sessionStorage.getItem(CLAIM_DISMISSED_KEY) === "1";
      } catch {
        claimDismissed = false;
      }
    }
    set({ sessionId, email, claimDismissed, hydrated: true });
  },
}));

/** Non-reactive accessor for the API client (outside React render). */
export function getStoredSessionId(): string | null {
  return useSessionStore.getState().sessionId ?? readLocal(SESSION_KEY);
}
