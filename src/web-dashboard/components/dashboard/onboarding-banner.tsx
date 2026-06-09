"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { onboardingProgress, useOnboardingStore } from "@/stores/onboarding-store";

export function OnboardingBanner() {
  const { steps, dismissed, dismiss } = useOnboardingStore();
  const progress = onboardingProgress(steps);
  const allComplete = progress === 100;

  if (dismissed || allComplete) return null;

  return (
    <div className="border-t border-border bg-primary/5 px-4 py-3">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">Complete your setup ({progress}%)</p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {steps.map((step) => (
              <span
                key={step.id}
                className={`text-xs ${step.completed ? "text-green-600 line-through" : "text-muted-foreground"}`}
              >
                {step.completed ? "✓" : "○"} {step.label}
              </span>
            ))}
          </div>
          <Link href="/onboarding" className="mt-2 inline-block text-xs font-medium text-primary hover:underline">
            View onboarding checklist →
          </Link>
        </div>
        <button
          type="button"
          onClick={dismiss}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Dismiss onboarding banner"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
