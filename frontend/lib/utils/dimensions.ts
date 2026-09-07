/**
 * Founder-facing labels for each scored dimension. Keyed by the agent
 * name the backend uses internally (models.documents.AgentResultRecord
 * .agent / orchestrator.state.AgentOutput.agent) — that key is never
 * shown as-is; constraint #4 keeps agent count, model names and routing
 * out of the UI, so this is the one place that translation happens.
 * Order here is display order everywhere a dimension list renders.
 */
export interface DimensionMeta {
  key: string;
  label: string;
  description: string;
}

export const DIMENSIONS: DimensionMeta[] = [
  { key: "problem", label: "Problem", description: "Is the pain real, specific, and frequent enough to matter." },
  { key: "solution", label: "Solution", description: "Does the fix map directly onto that pain." },
  { key: "tam", label: "Market Size", description: "Is the reachable market large enough to matter." },
  { key: "team", label: "Team", description: "Founder-market fit and ability to execute." },
  { key: "moat", label: "Moat", description: "What compounds and gets harder for others to copy." },
  { key: "unit_economics", label: "Unit Economics", description: "Pricing, acquisition cost, and margin health." },
  { key: "gtm", label: "Go-to-Market", description: "A specific first customer and a credible way to reach them." },
  { key: "risk", label: "Risk", description: "Technical, regulatory, and competitive exposure." },
  { key: "timing", label: "Timing", description: "Whether the market is ready for this right now." },
  { key: "ask", label: "Ask", description: "Clarity of the next concrete step." },
  { key: "yc_signal", label: "Founder Signal", description: "Acute pain, fast iteration, a simple wedge." },
  { key: "lovers_test", label: "Retention Pull", description: "Would early users genuinely miss it if it vanished." },
];

const byKey = new Map(DIMENSIONS.map((d) => [d.key, d]));

export function dimensionLabel(key: string): string {
  return byKey.get(key)?.label ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function dimensionDescription(key: string): string {
  return byKey.get(key)?.description ?? "";
}

export function orderDimensionKeys(keys: string[]): string[] {
  const known = DIMENSIONS.map((d) => d.key).filter((k) => keys.includes(k));
  const unknown = keys.filter((k) => !byKey.has(k));
  return [...known, ...unknown];
}
