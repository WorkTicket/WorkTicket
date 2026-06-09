/**
 * @deprecated v1 is manual-first. AI settings UI removed.
 * @see lib/product-rules.ts and docs/PRODUCT_RULES.md
 */

import { AI_FEATURES_ENABLED } from "@/lib/product-rules";

export type AiMode = "manual";

export interface AiSettings {
  mode: AiMode;
  enabled: false;
  analysisEnabled: false;
  suggestionsEnabled: false;
  estimateGeneration: false;
}

const lockedSettings: AiSettings = {
  mode: "manual",
  enabled: false,
  analysisEnabled: false,
  suggestionsEnabled: false,
  estimateGeneration: false,
};

/** No-op provider — AI is disabled in v1. Kept for import compatibility. */
export function AiSettingsProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useAiSettings() {
  return {
    settings: lockedSettings,
    setMode: () => {
      if (!AI_FEATURES_ENABLED && process.env.NODE_ENV !== "production") {
        console.warn("AI features are disabled in v1 (manual-first).");
      }
    },
    update: () => undefined,
    reset: () => undefined,
  };
}
