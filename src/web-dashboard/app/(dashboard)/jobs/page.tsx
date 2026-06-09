"use client";

import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useOnboardingStore } from "@/stores/onboarding-store";

interface Customer {
  id: string;
  name: string;
  phone?: string;
}

interface Job {
  id: string;
  description: string;
  address: string;
  status: string;
  customer_id: string;
}

function JobsPageContent() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const completeStep = useOnboardingStore((s) => s.completeStep);
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customersLoading, setCustomersLoading] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [description, setDescription] = useState("");
  const [address, setAddress] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ description?: string; address?: string }>({});

  const { data: jobs, isLoading, error: jobsError } = useQuery<{ jobs: Job[] }>({
    queryKey: ["jobs"],
    queryFn: () => api.get("/jobs").then((r) => r.data),
  });

  const loadCustomers = useCallback(async () => {
    setCustomersLoading(true);
    try {
      const res = await api.get("/jobs/customers");
      setCustomers((res.data.customers || []) as Customer[]);
    } catch {
      setError("Failed to load customers");
    } finally {
      setCustomersLoading(false);
    }
  }, []);

  const toggleCreateJob = useCallback(() => {
    setShowCreateJob((prev) => {
      const next = !prev;
      if (next) loadCustomers();
      return next;
    });
  }, [loadCustomers]);

  const validateJobForm = useCallback((): boolean => {
    const errors: { description?: string; address?: string } = {};
    if (!description || description.trim().length < 10) {
      errors.description = "Description must be at least 10 characters";
    }
    if (!address || !address.trim()) {
      errors.address = "Address is required";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }, [description, address]);

  const handleCreateJob = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setFieldErrors({});
      if (!selectedCustomer) {
        setFieldErrors({ description: "Please select a customer" });
        return;
      }
      if (!validateJobForm()) return;
      setCreating(true);
      try {
        const res = await api.post("/jobs", {
          customer_id: selectedCustomer,
          description: description.trim(),
          address: address.trim(),
        });
        setShowCreateJob(false);
        setSelectedCustomer("");
        setDescription("");
        setAddress("");
        completeStep("job");
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
        router.push(`/jobs/${res.data.id}`);
      } catch {
        setError("Failed to create job");
      } finally {
        setCreating(false);
      }
    },
    [selectedCustomer, description, address, queryClient, router, validateJobForm, completeStep]
  );

  const handleDeleteJob = useCallback(
    async (jobId: string) => {
      if (!confirm("Delete this job?")) return;
      try {
        setError(null);
        await api.delete(`/jobs/${jobId}`);
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      } catch {
        setError("Failed to delete job");
      }
    },
    [queryClient]
  );

  return (
    <div>
      <PageHeader
        title="Jobs"
        description="Manage jobs from lead through completion."
        actions={
          <Button onClick={toggleCreateJob}>
            {showCreateJob ? "Cancel" : "+ Create Job"}
          </Button>
        }
      />

      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {showCreateJob && (
        <form onSubmit={handleCreateJob} className="mb-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-4 font-semibold">New Job</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="customer-select" className="mb-1 block text-sm font-medium">
                Customer *
              </label>
              {customersLoading ? (
                <Spinner />
              ) : customers.length === 0 ? (
                <Link href="/customers" className="text-sm text-primary hover:underline">
                  Add a customer first →
                </Link>
              ) : (
                <select
                  id="customer-select"
                  value={selectedCustomer}
                  onChange={(e) => setSelectedCustomer(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  required
                >
                  <option value="">Select a customer...</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.phone ? `(${c.phone})` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label htmlFor="job-description" className="mb-1 block text-sm font-medium">
                Description *
              </label>
              <input
                id="job-description"
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={`w-full rounded-lg border px-3 py-2 text-sm ${fieldErrors.description ? "border-red-300" : "border-border"}`}
                placeholder="Job description (min 10 characters)"
              />
              {fieldErrors.description && (
                <p className="mt-1 text-xs text-red-500">{fieldErrors.description}</p>
              )}
            </div>
            <div>
              <label htmlFor="job-address" className="mb-1 block text-sm font-medium">
                Address *
              </label>
              <input
                id="job-address"
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className={`w-full rounded-lg border px-3 py-2 text-sm ${fieldErrors.address ? "border-red-300" : "border-border"}`}
                placeholder="Job address"
              />
              {fieldErrors.address && (
                <p className="mt-1 text-xs text-red-500">{fieldErrors.address}</p>
              )}
            </div>
            <Button type="submit" disabled={creating || !selectedCustomer}>
              {creating ? "Creating..." : "Create Job"}
            </Button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : jobsError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-600">
          Failed to load jobs
        </div>
      ) : !jobs?.jobs?.length ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-muted-foreground">
          No jobs yet. Create a job to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.jobs.map((job) => (
            <Link
              key={job.id}
              href={`/jobs/${job.id}`}
              className="block rounded-xl border border-border bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="truncate font-medium">{job.description || "No description"}</p>
                  <p className="text-sm text-muted-foreground">{job.address}</p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium">{job.status}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleDeleteJob(job.id);
                    }}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function JobsPage() {
  return (
    <PermissionGate permission="jobs:view">
      <JobsPageContent />
    </PermissionGate>
  );
}
