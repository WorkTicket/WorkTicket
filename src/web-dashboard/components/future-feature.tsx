import { FUTURE_FEATURE_LABEL, FUTURE_FEATURES, type FutureFeatureId } from "@/lib/product-rules";

interface FutureFeatureProps {
  featureId: FutureFeatureId;
  className?: string;
}

export function FutureFeature({ featureId, className = "" }: FutureFeatureProps) {
  const feature = FUTURE_FEATURES[featureId];

  return (
    <div
      className={`rounded-xl border border-dashed border-border bg-muted/30 p-6 ${className}`}
      aria-label={`${feature.title} — ${FUTURE_FEATURE_LABEL}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{feature.title}</h3>
        <span className="inline-flex rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950 dark:text-amber-200">
          {FUTURE_FEATURE_LABEL}
        </span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{feature.description}</p>
    </div>
  );
}
