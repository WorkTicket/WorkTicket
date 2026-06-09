import { FUTURE_FEATURE_LABEL } from "@/lib/product-rules";

export function ComingSoonBadge({ label = FUTURE_FEATURE_LABEL }: { label?: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950 dark:text-amber-300">
      {label}
    </span>
  );
}
