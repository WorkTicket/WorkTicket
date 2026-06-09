/**
 * WorkTicket v1 product rules — manual-first, AI disabled.
 * @see src/docs/PRODUCT_RULES.md
 */

/** Locked: AI is not enabled in v1. Do not flip without product + infra approval. */
export const AI_FEATURES_ENABLED = false as const;

export const FUTURE_FEATURE_LABEL = "Coming Soon" as const;

export const FUTURE_FEATURE_SUBLABELS = {
  advancedPlan: "Requires Advanced Plan (Future Release)",
  notAvailable: "Not available in current version",
} as const;

export type FutureFeatureId =
  | "voice_transcript"
  | "estimate_draft"
  | "job_summary"
  | "estimate_suggestions";

export const FUTURE_FEATURES: Record<
  FutureFeatureId,
  { title: string; description: string }
> = {
  voice_transcript: {
    title: "Voice Transcript",
    description: FUTURE_FEATURE_SUBLABELS.notAvailable,
  },
  estimate_draft: {
    title: "Draft Estimate",
    description: FUTURE_FEATURE_SUBLABELS.advancedPlan,
  },
  job_summary: {
    title: "Job Summary",
    description: FUTURE_FEATURE_SUBLABELS.notAvailable,
  },
  estimate_suggestions: {
    title: "Estimate Suggestions",
    description: FUTURE_FEATURE_SUBLABELS.advancedPlan,
  },
};
