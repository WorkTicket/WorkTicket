"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { onboardingProgress, useOnboardingStore } from "@/stores/onboarding-store";

export default function OnboardingPage() {
  const router = useRouter();
  const { user } = useUser();
  const { steps, completeStep } = useOnboardingStore();
  const [companyName, setCompanyName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const progress = onboardingProgress(steps);

  async function handleCreateCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !companyName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.post("/auth/register", {
        user_id: user.id,
        email: user.primaryEmailAddress?.emailAddress ?? "",
        name: user.fullName ?? user.firstName ?? "User",
        company_name: companyName.trim(),
      });
      completeStep("company");
    } catch {
      setError("Failed to create company. It may already exist — try continuing to the dashboard.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-3xl font-bold text-foreground">Welcome to WorkTicket</h1>
      <p className="mt-2 text-muted-foreground">Complete these steps to get the most out of your account.</p>

      <div className="mt-6 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{progress}% complete</p>

      {!steps.find((s) => s.id === "company")?.completed && (
        <form onSubmit={handleCreateCompany} className="mt-8 rounded-xl border border-border bg-card p-6">
          <h2 className="font-semibold">Step 1: Create your company</h2>
          <label htmlFor="company-name" className="mt-4 block text-sm font-medium">
            Company name
          </label>
          <input
            id="company-name"
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm"
            placeholder="ABC Plumbing"
            required
          />
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <Button type="submit" className="mt-4" disabled={loading}>
            {loading ? "Creating..." : "Create Company"}
          </Button>
        </form>
      )}

      <ol className="mt-8 space-y-4">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`flex items-center gap-3 rounded-lg border p-4 ${
              step.completed ? "border-green-200 bg-green-50" : "border-border bg-card"
            }`}
          >
            <span
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                step.completed ? "bg-green-600 text-white" : "bg-muted text-muted-foreground"
              }`}
            >
              {step.completed ? "✓" : index + 1}
            </span>
            <span className={step.completed ? "text-green-800 line-through" : "text-foreground"}>
              {step.label}
            </span>
          </li>
        ))}
      </ol>

      <div className="mt-8 flex gap-3">
        <Button onClick={() => router.push("/dashboard")}>Go to Dashboard</Button>
        <Button variant="secondary" onClick={() => router.push("/customers")}>
          Add First Customer
        </Button>
      </div>
    </div>
  );
}
