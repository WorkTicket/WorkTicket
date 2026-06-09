"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";
import { FutureFeature } from "@/components/future-feature";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";

interface Estimate {
  id: string;
  title: string;
  status: string;
  created_at?: string;
  total: number;
}

function EstimatesPageContent() {
  const { data, isLoading } = useQuery<{ estimates: Estimate[]; total: number }>({
    queryKey: ["estimates"],
    queryFn: () => api.get("/estimates").then((r) => r.data).catch(() => ({ estimates: [], total: 0 })),
  });

  return (
    <div>
      <PageHeader
        title="Estimates"
        description="Create, edit, and send estimates to customers — all line items are entered manually."
      />

      <FutureFeature featureId="estimate_draft" className="mb-6" />

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : !data?.estimates?.length ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-muted-foreground">
          No estimates yet. Create an estimate from a job to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {data.estimates.map((est) => (
            <Link
              key={est.id}
              href={`/estimates/${est.id}`}
              className="block rounded-xl border border-border bg-card p-4 shadow-sm hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{est.title || "Untitled Estimate"}</p>
                  <p className="text-sm text-muted-foreground">{est.status.replace("_", " ")}</p>
                </div>
                <p className="text-lg font-bold text-primary">${est.total?.toFixed(2)}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function EstimatesPage() {
  return (
    <PermissionGate permission="estimates:view">
      <EstimatesPageContent />
    </PermissionGate>
  );
}
