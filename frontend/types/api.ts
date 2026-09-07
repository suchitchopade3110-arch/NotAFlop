/**
 * Types mirroring models/schemas.py and models/documents.py on the
 * backend. Kept hand-in-sync deliberately (no codegen) since the backend
 * is frozen for this phase — see the "no backend changes" constraint.
 */

// ── Filter (Phase 1) ────────────────────────────────────────────────
export interface AgentResult {
  passed: boolean;
  score: number; // 0-10
  feedback: string;
}

export interface FilterResponse {
  verdict: "pass" | "fail";
  narrow_problem: AgentResult;
  pitch_clarity: AgentResult;
  feedback: string | null;
}

export interface TranscribeResponse {
  transcript: string;
}

// ── Smart data layer (Phase 2 backend / signals) ─────────────────────
// Shape is intentionally loose (dict on the backend) — the UI reads only
// the keys it needs and treats everything else as opaque.
export type SignalsPayload = Record<string, unknown>;

// ── Streaming analyze (Phase 3) ───────────────────────────────────────
export interface AgentOutput {
  agent: string;
  passed: boolean;
  score: number; // 0-10
  evidence: string;
  feedback: string;
}

export interface SignalQualityPayload {
  signal_quality: number; // 0-1
  low_confidence: boolean;
  signal_quality_by_source: Record<string, number>;
  conflicts: ConflictEntry[];
}

export interface ConflictEntry {
  dimension?: string;
  sources?: string[];
  directions?: string[];
  description?: string;
  [key: string]: unknown;
}

export interface FinalPayload {
  public_id: string | null;
  score: number;
  verdict: "go" | "pivot" | "no-go";
  errors: string[];
}

export type StreamEvent =
  | { type: "signal_quality"; payload: SignalQualityPayload }
  | { type: "agent"; payload: AgentOutput }
  | { type: "agent_error"; payload: { agent: string; error: string } }
  | { type: "final"; payload: FinalPayload };

// ── Reports (persistence) ─────────────────────────────────────────────
export interface AgentResultRecord {
  agent: string;
  passed: boolean;
  score: number;
  evidence: string;
  feedback: string;
  model: string;
}

export interface VerifierOutput {
  agent: "verifier";
  confidence_score: number;
  passed: boolean;
  conflicts: string[];
  evidence: string;
  feedback: string;
  model: string;
}

export interface ReportResponse {
  public_id: string;
  idea_hash: string;
  transcript: string;
  keyword: string;
  signals: SignalsPayload;
  filter_result: FilterResponse | null;
  agent_results: Record<string, AgentResultRecord>;
  verifier: VerifierOutput | null;
  signal_quality: number;
  signal_quality_by_source: Record<string, number>;
  low_confidence: boolean;
  conflicts: ConflictEntry[];
  report_cost_usd: number;
  weights_version: number;
  raw_score: number;
  adjusted_score: number | null;
  verdict: string;
  gating_score: "raw" | "adjusted";
  verdict_would_flip: boolean;
  tier_reached: number;
  created_at: string;
  updated_at: string;
}

export interface ReportSummary {
  public_id: string;
  keyword: string;
  raw_score: number;
  verdict: string;
  tier_reached: number;
  created_at: string;
}

export interface RateLimitErrorBody {
  limit: number;
  remaining: number;
  reset_at: string;
  scope: "session" | "ip";
}

// ── Progressive identity ──────────────────────────────────────────────
export interface SessionResponse {
  session_id: string;
}

export interface ClaimResponse {
  status: "sent";
}

export interface VerifyResponse {
  account_id: string;
  email: string;
  session_id: string;
  claimed_ideas: number;
}

export interface MeResponse {
  session_id: string;
  account_id: string | null;
  email: string | null;
  plan: string | null;
  owned_idea_count: number;
  report_count: number;
}

// ── The log surface ────────────────────────────────────────────────────
export interface IdeaSummary {
  idea_id: string;
  keyword: string;
  raw_score: number | null;
  verdict: string | null;
  status: string;
  last_snapshot_at: string | null;
  created_at: string;
}

export interface IdeaDetailResponse {
  idea_id: string;
  raw_text: string;
  keyword: string;
  status: string;
  share_token: string;
  current_snapshot_id: string | null;
  weights_version: number | null;
  raw_score: number | null;
  verdict: string | null;
  created_at: string;
  updated_at: string;
}

export interface SnapshotSummary {
  snapshot_id: string;
  trigger: "initial" | "scheduled" | "evidence" | "manual";
  raw_score: number;
  verdict: string;
  weights_version: number;
  deltas: Record<string, unknown>;
  version_crossing: boolean;
  cost: number;
  created_at: string;
}

export interface ShareCardResponse {
  verdict: string;
  raw_score: number;
  keyword: string;
  top_reasons: string[];
  created_at: string;
}

export type TimelineEntryType = "snapshot" | "evidence" | "milestone" | "criterion";

export interface TimelineEntry {
  type: TimelineEntryType;
  at: string;
  payload: Record<string, unknown>;
}

// ── Kill criteria ──────────────────────────────────────────────────────
export interface CriterionResponse {
  criterion_id: string;
  idea_id: string;
  statement: string;
  metric: string;
  threshold: string;
  deadline: string;
  status: "pending" | "met" | "failed" | "lapsed";
  resolved_at: string | null;
  resolution_note: string | null;
  created_at: string;
}

// ── Evidence and milestones ────────────────────────────────────────────
export type EvidenceType = "interview" | "waitlist" | "revenue" | "letter_of_intent" | "other";

export interface EvidenceResponse {
  evidence_id: string;
  idea_id: string;
  type: string;
  payload: Record<string, unknown>;
  submitted_at: string;
  triggered_snapshot_id: string | null;
  snapshot: SnapshotSummary | null;
}

export interface MilestoneResponse {
  milestone_id: string;
  day_range: string;
  block_title: string;
  tasks: string[];
  deliverable: string;
  completed: boolean;
  completed_at: string | null;
  evidence_id: string | null;
}

// ── Plan (Phase 5) ──────────────────────────────────────────────────────
export interface RoadmapMilestone {
  day_range: string;
  block_title: string;
  tasks: string[];
  deliverable: string;
  risk_flags: string[];
}

export interface TeamRole {
  role: string;
  priority: "critical" | "important" | "nice_to_have";
  reason: string;
  skills: string[];
  where_to_find: string[];
}

export interface PlanResponse {
  roadmap: RoadmapMilestone[];
  team: TeamRole[];
  revenue_model_options: string[];
  solo_founder_note: string | null;
}

// ── Generic API error shape ────────────────────────────────────────────
export interface ApiErrorBody {
  detail: string | Record<string, unknown> | RateLimitErrorBody;
}
