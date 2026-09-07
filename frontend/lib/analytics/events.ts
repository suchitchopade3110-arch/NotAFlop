import { capture } from "@/lib/analytics/posthog";

/**
 * The funnel (D1): landing -> pitch submitted -> report completed ->
 * claim prompt shown -> claimed -> returned. Every function here takes
 * only non-sensitive, structural properties (scores, verdicts, counts,
 * booleans) — never pitch text, email addresses, or evidence payloads.
 * lib/analytics/posthog.ts's capture() also strips any forbidden key as
 * a second layer, so a mistake here still can't leak content.
 */
export const track = {
  landingViewed: () => capture("landing_viewed"),

  pitchSubmitted: (properties: { input_mode: "text" | "audio" | "video"; length: number }) =>
    capture("pitch_submitted", properties),

  filterFailed: () => capture("filter_failed"),

  filterRevised: () => capture("filter_revised"),

  streamStarted: () => capture("stream_started"),

  streamDropped: (properties: { agents_landed: number }) => capture("stream_dropped", properties),

  streamRecovered: () => capture("stream_recovered"),

  reportCompleted: (properties: { verdict: string; score: number; low_confidence: boolean }) =>
    capture("report_completed", properties),

  claimPromptShown: () => capture("claim_prompt_shown"),

  claimPromptDismissed: () => capture("claim_prompt_dismissed"),

  claimSubmitted: () => capture("claim_submitted"),

  claimed: () => capture("claimed"),

  returned: (properties: { owned_idea_count: number }) => capture("returned", properties),

  ideaPromoted: () => capture("idea_promoted"),

  criterionCreated: () => capture("criterion_created"),

  evidenceSubmitted: (properties: { type: string }) => capture("evidence_submitted", properties),

  shareCardViewed: (properties: { verdict: string }) => capture("share_card_viewed", properties),

  comingSoonSignup: () => capture("coming_soon_signup"),
};
