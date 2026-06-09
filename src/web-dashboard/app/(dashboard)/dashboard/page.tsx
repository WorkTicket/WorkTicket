"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ClipboardList,
  DollarSign,
  FileText,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { api } from "@/lib/api";

export default function DashboardOverviewPage() {
  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.get("/jobs").then((r) => r.data),
  });

  const { data: estimates } = useQuery({
    queryKey: ["estimates"],
    queryFn: () => api.get("/estimates").then((r) => r.data).catch(() => ({ estimates: [], total: 0 })),
  });

  const { data: customers } = useQuery({
    queryKey: ["customers"],
    queryFn: () => api.get("/jobs/customers").then((r) => r.data).catch(() => ({ customers: [] })),
  });

  const activeJobs =
    jobs?.jobs?.filter((j: { status: string }) => ["in_progress", "pending"].includes(j.status))
      .length ?? 0;
  const openEstimates =
    estimates?.estimates?.filter((e: { status: string }) => !["approved", "rejected"].includes(e.status))
      .length ?? 0;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Overview of your jobs, estimates, and team activity."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active Jobs" value={activeJobs} icon={ClipboardList} />
        <StatCard label="Open Estimates" value={openEstimates} icon={FileText} />
        <StatCard label="Customers" value={customers?.customers?.length ?? 0} icon={Users} />
        <StatCard label="Revenue This Month" value="—" icon={DollarSign} trend="Connect billing API" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-foreground">Recent Jobs</h2>
            <Link href="/jobs" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          <ul className="mt-4 space-y-3">
            {(jobs?.jobs ?? []).slice(0, 5).map((job: { id: string; description: string; status: string }) => (
              <li key={job.id}>
                <Link href={`/jobs/${job.id}`} className="flex items-center justify-between rounded-lg p-2 hover:bg-muted">
                  <span className="truncate text-sm font-medium">{job.description || "Untitled job"}</span>
                  <span className="ml-2 shrink-0 text-xs text-muted-foreground">{job.status}</span>
                </Link>
              </li>
            ))}
            {!jobs?.jobs?.length && (
              <p className="text-sm text-muted-foreground">No jobs yet. Create your first job to get started.</p>
            )}
          </ul>
        </section>

        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold text-foreground">Recent Activity</h2>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            Team activity feed will appear here as your crew updates jobs, uploads photos, and
            records notes.
          </p>
        </section>
      </div>
    </div>
  );
}
