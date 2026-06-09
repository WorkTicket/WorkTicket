import { ApiTokenSync } from "@/components/dashboard/api-token-sync";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <ApiTokenSync />
      {children}
    </div>
  );
}
