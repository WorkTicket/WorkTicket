/**
 * @deprecated Use FutureFeature from @/components/future-feature instead.
 * AiSection never renders children in v1 — manual-first product rule.
 */

import type { ReactNode } from "react";
import { AI_FEATURES_ENABLED } from "@/lib/product-rules";

type AiSectionProps = {
  feature: string;
  children: ReactNode;
  fallback?: ReactNode;
};

export function AiSection({ children, fallback }: AiSectionProps) {
  if (AI_FEATURES_ENABLED) {
    return <>{children}</>;
  }
  if (fallback) {
    return <>{fallback}</>;
  }
  return null;
}
