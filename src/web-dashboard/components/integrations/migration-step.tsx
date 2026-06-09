"use client";

import { Check } from "lucide-react";

interface Step {
  id: string;
  label: string;
  description: string;
}

interface MigrationStepIndicatorProps {
  steps: Step[];
  currentStep: number;
  completedSteps: Set<number>;
}

export function MigrationStepIndicator({ steps, currentStep, completedSteps }: MigrationStepIndicatorProps) {
  return (
    <div className="mb-8">
      <nav aria-label="Migration progress" className="flex items-center justify-between">
        {steps.map((step, index) => {
          const stepNum = index + 1;
          const isActive = stepNum === currentStep;
          const isComplete = completedSteps.has(stepNum);

          return (
            <div key={step.id} className="flex flex-1 items-center">
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors ${
                    isComplete
                      ? "border-green-500 bg-green-500 text-white"
                      : isActive
                        ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-900/30"
                        : "border-gray-300 bg-white text-gray-400 dark:border-gray-600 dark:bg-gray-800"
                  }`}
                >
                  {isComplete ? <Check className="h-4 w-4" /> : stepNum}
                </div>
                <span
                  className={`mt-1.5 text-xs font-medium ${
                    isActive ? "text-blue-600 dark:text-blue-400" : "text-muted-foreground"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`mx-2 h-0.5 flex-1 ${
                    isComplete ? "bg-green-500" : "bg-gray-200 dark:bg-gray-700"
                  }`}
                />
              )}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

export const MIGRATION_STEPS: Step[] = [
  { id: "connect", label: "Connect", description: "Link your existing system" },
  { id: "scan", label: "Scan", description: "Discover your data" },
  { id: "preview", label: "Preview", description: "Review what will be imported" },
  { id: "import", label: "Import", description: "Bring your data into WorkTicket" },
  { id: "done", label: "Done", description: "Migration complete" },
];
