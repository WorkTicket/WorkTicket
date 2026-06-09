import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OnboardingStep {
  id: string;
  label: string;
  completed: boolean;
}

interface OnboardingState {
  steps: OnboardingStep[];
  dismissed: boolean;
  completeStep: (id: string) => void;
  dismiss: () => void;
  reset: () => void;
}

const defaultSteps: OnboardingStep[] = [
  { id: "company", label: "Create company", completed: false },
  { id: "customer", label: "Add first customer", completed: false },
  { id: "job", label: "Create first job", completed: false },
  { id: "photo", label: "Upload first photo", completed: false },
  { id: "invite", label: "Invite first employee", completed: false },
];

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      steps: defaultSteps,
      dismissed: false,
      completeStep: (id) =>
        set((state) => ({
          steps: state.steps.map((s) => (s.id === id ? { ...s, completed: true } : s)),
        })),
      dismiss: () => set({ dismissed: true }),
      reset: () => set({ steps: defaultSteps, dismissed: false }),
    }),
    { name: "workticket-onboarding" }
  )
);

export function onboardingProgress(steps: OnboardingStep[]): number {
  const completed = steps.filter((s) => s.completed).length;
  return Math.round((completed / steps.length) * 100);
}
