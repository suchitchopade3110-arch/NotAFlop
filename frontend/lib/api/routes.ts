import { apiFetch } from "@/lib/api/client";
import type {
  ClaimResponse,
  CriterionResponse,
  EvidenceResponse,
  EvidenceType,
  FilterResponse,
  IdeaDetailResponse,
  IdeaSummary,
  MeResponse,
  MilestoneResponse,
  PlanResponse,
  ReportResponse,
  ReportSummary,
  SessionResponse,
  ShareCardResponse,
  SignalsPayload,
  SnapshotSummary,
  TimelineEntry,
  TranscribeResponse,
  VerifyResponse,
} from "@/types/api";

// ── Session (A3) ────────────────────────────────────────────────────
export const mintSession = () => apiFetch<SessionResponse>("/v1/session", { method: "POST", body: {} });

export const getMe = () => apiFetch<MeResponse>("/v1/me");

// ── Phase 1 — Filter ────────────────────────────────────────────────
export const transcribeAudio = (file: File) => {
  const form = new FormData();
  form.append("audio", file);
  return apiFetch<TranscribeResponse>("/api/phase1/transcribe", { method: "POST", body: form });
};

export const runFilter = (transcript: string) =>
  apiFetch<FilterResponse>("/api/phase1/filter", { method: "POST", body: { transcript } });

// ── Phase 2 — Smart data layer ─────────────────────────────────────
export const gatherSignals = (keyword: string) =>
  apiFetch<SignalsPayload>("/api/phase2/validate", { method: "POST", body: { keyword } });

// Streaming analyze lives in lib/api/stream.ts (needs raw body access).

// ── Reports ─────────────────────────────────────────────────────────
export const getReport = (publicId: string) => apiFetch<ReportResponse>(`/api/reports/${publicId}`);

export const listSessionReports = (sessionId: string) =>
  apiFetch<ReportSummary[]>(`/api/sessions/${sessionId}/reports`);

// ── Phase 5 — Plan ──────────────────────────────────────────────────
export const generatePlan = (reportId: string) =>
  apiFetch<PlanResponse>("/api/phase5/plan", { method: "POST", body: { report_id: reportId } });

// ── Progressive identity (B5 claim flow) ───────────────────────────
export const claimEmail = (email: string) =>
  apiFetch<ClaimResponse>("/v1/auth/claim", { method: "POST", body: { email } });

export const verifyClaimToken = (token: string) =>
  apiFetch<VerifyResponse>("/v1/auth/verify", { method: "POST", body: { token } });

// ── The log surface (C1/C2) ────────────────────────────────────────
export const promoteIdea = (reportId: string) =>
  apiFetch<IdeaDetailResponse>("/v1/ideas", { method: "POST", body: { report_id: reportId } });

export const listIdeas = () => apiFetch<IdeaSummary[]>("/v1/ideas");

export const getIdea = (ideaId: string) => apiFetch<IdeaDetailResponse>(`/v1/ideas/${ideaId}`);

export const deleteIdea = (ideaId: string) =>
  apiFetch<void>(`/v1/ideas/${ideaId}`, { method: "DELETE" });

export const listSnapshots = (ideaId: string) =>
  apiFetch<SnapshotSummary[]>(`/v1/ideas/${ideaId}/snapshots`);

export const forceSnapshot = (ideaId: string) =>
  apiFetch<SnapshotSummary>(`/v1/ideas/${ideaId}/snapshots`, { method: "POST", body: {} });

export const getTimeline = (ideaId: string) =>
  apiFetch<TimelineEntry[]>(`/v1/ideas/${ideaId}/timeline`);

// ── Kill criteria (C3) ─────────────────────────────────────────────
export interface CreateCriterionInput {
  statement: string;
  metric: string;
  threshold: string;
  deadline: string; // ISO datetime
}

export const createCriterion = (ideaId: string, input: CreateCriterionInput) =>
  apiFetch<CriterionResponse>(`/v1/ideas/${ideaId}/criteria`, { method: "POST", body: input });

export const listCriteria = (ideaId: string) =>
  apiFetch<CriterionResponse[]>(`/v1/ideas/${ideaId}/criteria`);

export const resolveCriterion = (criterionId: string, outcome: "met" | "failed", note: string) =>
  apiFetch<CriterionResponse>(`/v1/criteria/${criterionId}/resolve`, {
    method: "POST",
    body: { outcome, note },
  });

// ── Evidence and milestones (C4) ───────────────────────────────────
export const submitEvidence = (ideaId: string, type: EvidenceType, payload: Record<string, unknown>) =>
  apiFetch<EvidenceResponse>(`/v1/ideas/${ideaId}/evidence`, {
    method: "POST",
    body: { type, payload },
  });

export const listMilestones = (ideaId: string) =>
  apiFetch<MilestoneResponse[]>(`/v1/ideas/${ideaId}/milestones`);

export const patchMilestone = (milestoneId: string, completed: boolean, evidenceId?: string) =>
  apiFetch<MilestoneResponse>(`/v1/milestones/${milestoneId}`, {
    method: "PATCH",
    body: { completed, evidence_id: evidenceId ?? null },
  });

// ── Public share card (C5) ─────────────────────────────────────────
export const getShareCard = (token: string) => apiFetch<ShareCardResponse>(`/v1/share/${token}`);

export type { ReportSummary };
