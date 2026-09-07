"use client";

import { useEffect, useState } from "react";
import { computeGate } from "@/lib/api/routes";
import type { DimensionResult } from "@/lib/hooks/use-validation-flow";
import type { RiskItem } from "@/types/api";

interface GateReasonState {
  gateReason: string | null;
  topRisks: RiskItem[];
  loading: boolean;
}

/** Enriches the verdict with the one-sentence gate reason + top risks
 * from POST /api/phase4/gate — a read-only re-derivation from the same
 * agent results the stream already delivered, not a rescore. Purely an
 * enhancement: if it fails, the verdict view still renders fully. */
export function useGateReason(dimensions: DimensionResult[]): GateReasonState {
  const [state, setState] = useState<GateReasonState>({ gateReason: null, topRisks: [], loading: true });

  useEffect(() => {
    if (dimensions.length === 0) {
      setState({ gateReason: null, topRisks: [], loading: false });
      return;
    }
    let cancelled = false;
    const results = Object.fromEntries(
      dimensions.map((d) => [d.key, { agent: d.key, passed: d.passed, score: d.score, evidence: d.evidence, feedback: d.feedback }]),
    );
    computeGate(results)
      .then((res) => {
        if (!cancelled) setState({ gateReason: res.gate_reason, topRisks: res.top_risks, loading: false });
      })
      .catch(() => {
        if (!cancelled) setState({ gateReason: null, topRisks: [], loading: false });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dimensions.length]);

  return state;
}
