"use client";

import { useCallback, useRef, useState } from "react";
import { runFilter, gatherSignals, listSessionReports, getReport } from "@/lib/api/routes";
import { streamAnalyze, StreamConnectionError } from "@/lib/api/stream";
import { heuristicKeyword } from "@/lib/utils/keyword";
import { getStoredSessionId } from "@/lib/store/session";
import { describeError, type ErrorCopy } from "@/lib/utils/error-message";
import { track } from "@/lib/analytics/events";
import type { AgentOutput, FilterResponse, SignalQualityPayload } from "@/types/api";

export type FlowStage =
  | "idle"
  | "filtering"
  | "filter_failed"
  | "connecting"
  | "streaming"
  | "recovering"
  | "verdict"
  | "error";

export interface DimensionResult {
  key: string;
  score: number;
  passed: boolean;
  evidence: string;
  feedback: string;
}

export interface VerdictData {
  publicId: string | null;
  score: number;
  verdict: "go" | "pivot" | "no-go";
  dimensions: DimensionResult[];
  signalQuality: SignalQualityPayload | null;
  errors: string[];
  recovered: boolean;
}

const RECOVERY_POLL_MS = 3500;
const RECOVERY_MAX_ATTEMPTS = 18; // ~63s

function toDimension(key: string, out: AgentOutput): DimensionResult {
  return { key, score: out.score, passed: out.passed, evidence: out.evidence, feedback: out.feedback };
}

export function useValidationFlow() {
  const [stage, setStage] = useState<FlowStage>("idle");
  const [transcript, setTranscript] = useState("");
  const [filterResult, setFilterResult] = useState<FilterResponse | null>(null);
  const [dimensions, setDimensions] = useState<DimensionResult[]>([]);
  const [signalQuality, setSignalQuality] = useState<SignalQualityPayload | null>(null);
  const [verdict, setVerdict] = useState<VerdictData | null>(null);
  const [errorCopy, setErrorCopy] = useState<ErrorCopy | null>(null);
  const [recoveryAttempt, setRecoveryAttempt] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const submittedAtRef = useRef<string | null>(null);
  const landedCountRef = useRef(0);
  const cancelledRef = useRef(false);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    cancelledRef.current = true;
    setStage("idle");
    setFilterResult(null);
    setDimensions([]);
    setSignalQuality(null);
    setVerdict(null);
    setErrorCopy(null);
    setRecoveryAttempt(0);
    landedCountRef.current = 0;
  }, []);

  const attemptRecovery = useCallback(async (submittedAt: string) => {
    for (let attempt = 1; attempt <= RECOVERY_MAX_ATTEMPTS; attempt++) {
      if (cancelledRef.current) return;
      setRecoveryAttempt(attempt);
      await new Promise((resolve) => setTimeout(resolve, RECOVERY_POLL_MS));
      if (cancelledRef.current) return;

      const sessionId = getStoredSessionId();
      if (!sessionId) continue;

      try {
        const reports = await listSessionReports(sessionId);
        const candidate = reports.find((r) => new Date(r.created_at).getTime() >= new Date(submittedAt).getTime() - 5000);
        if (!candidate) continue;

        const full = await getReport(candidate.public_id);
        const dims = Object.entries(full.agent_results).map(([key, record]) =>
          toDimension(key, {
            agent: record.agent,
            passed: record.passed,
            score: record.score,
            evidence: record.evidence,
            feedback: record.feedback,
          }),
        );
        setVerdict({
          publicId: full.public_id,
          score: full.raw_score,
          verdict: full.verdict as VerdictData["verdict"],
          dimensions: dims,
          signalQuality: {
            signal_quality: full.signal_quality,
            low_confidence: full.low_confidence,
            signal_quality_by_source: full.signal_quality_by_source,
            conflicts: full.conflicts,
          },
          errors: [],
          recovered: true,
        });
        track.streamRecovered();
        track.reportCompleted({ verdict: full.verdict, score: full.raw_score, low_confidence: full.low_confidence });
        setStage("verdict");
        return;
      } catch {
        // keep polling — a transient error here shouldn't end recovery early
      }
    }

    if (!cancelledRef.current) {
      setErrorCopy({
        title: "Still working on it",
        description:
          "Your analysis may still be finishing on our servers. Check your log in a minute, or start a new validation.",
      });
      setStage("error");
    }
  }, []);

  const runStream = useCallback(
    async (finalTranscript: string, keyword: string, signals: Record<string, unknown>, filterPayload: unknown) => {
      cancelledRef.current = false;
      landedCountRef.current = 0;
      setDimensions([]);
      setSignalQuality(null);
      setStage("connecting");
      track.streamStarted();

      const controller = new AbortController();
      abortRef.current = controller;
      const submittedAt = new Date().toISOString();
      submittedAtRef.current = submittedAt;

      let sawFinal = false;
      let finalScore = 0;
      let finalVerdict: VerdictData["verdict"] = "no-go";
      let finalErrors: string[] = [];
      let finalPublicId: string | null = null;
      let sq: SignalQualityPayload | null = null;
      const dims: DimensionResult[] = [];

      try {
        for await (const event of streamAnalyze({
          transcript: finalTranscript,
          signals,
          filterResult: filterPayload,
          signal: controller.signal,
        })) {
          if (event.type === "signal_quality") {
            sq = event.payload;
            setSignalQuality(event.payload);
            setStage("streaming");
          } else if (event.type === "agent") {
            landedCountRef.current += 1;
            const dim = toDimension(event.payload.agent, event.payload);
            dims.push(dim);
            setDimensions((prev) => [...prev, dim]);
            setStage("streaming");
          } else if (event.type === "agent_error") {
            landedCountRef.current += 1;
            const dim: DimensionResult = {
              key: event.payload.agent,
              score: 0,
              passed: false,
              evidence: "",
              feedback: "This dimension could not be scored. It's treated as missing, not as a zero.",
            };
            dims.push(dim);
            setDimensions((prev) => [...prev, dim]);
          } else if (event.type === "final") {
            sawFinal = true;
            finalScore = event.payload.score;
            finalVerdict = event.payload.verdict;
            finalErrors = event.payload.errors;
            finalPublicId = event.payload.public_id;
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof StreamConnectionError) {
          track.streamDropped({ agents_landed: landedCountRef.current });
          setStage("recovering");
          void attemptRecovery(submittedAt);
          return;
        }
        setErrorCopy(describeError(err));
        setStage("error");
        return;
      }

      if (!sawFinal) {
        track.streamDropped({ agents_landed: landedCountRef.current });
        setStage("recovering");
        void attemptRecovery(submittedAt);
        return;
      }

      const result: VerdictData = {
        publicId: finalPublicId,
        score: finalScore,
        verdict: finalVerdict,
        dimensions: dims,
        signalQuality: sq,
        errors: finalErrors,
        recovered: false,
      };
      setVerdict(result);
      track.reportCompleted({
        verdict: finalVerdict,
        score: finalScore,
        low_confidence: sq?.low_confidence ?? false,
      });
      setStage("verdict");
    },
    [attemptRecovery],
  );

  const submitPitch = useCallback(
    async (pitchText: string, inputMode: "text" | "audio" | "video") => {
      cancelledRef.current = false;
      setTranscript(pitchText);
      setStage("filtering");
      setErrorCopy(null);
      track.pitchSubmitted({ input_mode: inputMode, length: pitchText.length });

      try {
        const filter = await runFilter(pitchText);
        setFilterResult(filter);

        if (filter.verdict === "fail") {
          track.filterFailed();
          setStage("filter_failed");
          return;
        }

        const keyword = heuristicKeyword(pitchText);
        const signalsRes = await gatherSignals(keyword).catch(() => ({ keyword, signals: {} }));

        await runStream(pitchText, keyword, signalsRes.signals, filter);
      } catch (err) {
        setErrorCopy(describeError(err));
        setStage("error");
      }
    },
    [runStream],
  );

  const reviseAndRetry = useCallback((revisedText: string) => {
    setTranscript(revisedText);
    setFilterResult(null);
    setStage("idle");
    track.filterRevised();
  }, []);

  return {
    stage,
    transcript,
    filterResult,
    dimensions,
    signalQuality,
    verdict,
    errorCopy,
    recoveryAttempt,
    recoveryMaxAttempts: RECOVERY_MAX_ATTEMPTS,
    submitPitch,
    reviseAndRetry,
    reset,
  };
}
