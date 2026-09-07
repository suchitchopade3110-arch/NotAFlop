import { Card } from "@/components/ui/card";

interface RecoveringViewProps {
  attempt: number;
  maxAttempts: number;
}

/** B3: "Connection drop mid-stream: reconnect or degrade to a clear
 * recoverable state. Never a blank screen or a half-verdict presented
 * as complete." The backend keeps running the pipeline after a client
 * disconnect (see orchestrator/graph.py), so this polls the founder's
 * own report list for the result rather than re-submitting the pitch
 * (which would burn another daily validation and cost real money). */
export function RecoveringView({ attempt, maxAttempts }: RecoveringViewProps) {
  return (
    <section className="mx-auto flex w-full max-w-lg flex-col items-center px-6 py-24 text-center">
      <Card elevation="raised" className="w-full">
        <div className="mx-auto size-10 animate-pulse-soft rounded-full border-2 border-gold/50" aria-hidden="true" />
        <p className="mt-4 text-heading-sm text-ink">Connection dropped, still checking</p>
        <p className="mt-2 text-body text-ink-muted">
          Your analysis keeps running on our servers even when the connection drops. We&apos;re
          checking for your finished verdict now.
        </p>
        <p className="mt-4 text-mono text-ink-faint" role="status" aria-live="polite">
          Attempt {attempt} of {maxAttempts}
        </p>
      </Card>
    </section>
  );
}
