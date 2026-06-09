"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/dashboard/page-header";
import { FutureFeature } from "@/components/future-feature";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { usePermissions } from "@/lib/hooks/use-permissions";

interface MediaItem {
  type: string;
}

interface JobData {
  status: string;
  description?: string;
  address?: string;
  customer_id?: string;
  created_at?: string;
}

const COMPLETABLE_STATUSES = new Set(["pending", "in_progress"]);

export default function JobDetailPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const { can } = usePermissions();
  const [completing, setCompleting] = useState(false);
  const [completeError, setCompleteError] = useState<string | null>(null);

  const { data: job, isLoading, error } = useQuery<JobData>({
    queryKey: ["job", id],
    queryFn: () => api.get(`/jobs/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: media } = useQuery<{ media: MediaItem[] }>({
    queryKey: ["job-media", id],
    queryFn: () => api.get(`/media/${id}`).then((r) => r.data).catch(() => ({ media: [] })),
    enabled: !!id,
  });

  const handleMarkComplete = useCallback(async () => {
    if (!id || !job || completing || !COMPLETABLE_STATUSES.has(job.status)) return;
    setCompleting(true);
    setCompleteError(null);
    try {
      await api.patch(`/jobs/${id}`, { status: "completed" });
      await queryClient.invalidateQueries({ queryKey: ["job", id] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    } catch {
      setCompleteError("Failed to mark job as complete. Please try again.");
    } finally {
      setCompleting(false);
    }
  }, [id, job, completing, queryClient]);

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <p className="font-medium text-red-700">Failed to load job</p>
        <Link href="/jobs" className="mt-4 inline-block text-sm text-primary hover:underline">
          Back to jobs
        </Link>
      </div>
    );
  }

  const photos = media?.media?.filter((m) => m.type === "photo") ?? [];
  const audio = media?.media?.filter((m) => m.type === "audio") ?? [];
  const canComplete = can("jobs:manage") && job && COMPLETABLE_STATUSES.has(job.status);

  return (
    <div>
      <PageHeader
        title="Job Detail"
        description={job?.description || "Job information and attachments"}
        actions={
          <div className="flex items-center gap-3">
            {canComplete && (
              <Button onClick={handleMarkComplete} disabled={completing}>
                {completing ? "Completing..." : "Mark Complete"}
              </Button>
            )}
            <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize">
              {job?.status || "unknown"}
            </span>
          </div>
        }
      />

      {completeError && (
        <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {completeError}
        </div>
      )}

      {job?.status === "completed" && (
        <div className="mb-4 rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          This job has been marked complete.
        </div>
      )}

      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="font-semibold text-foreground">Job Information</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-muted-foreground">Description</dt>
            <dd className="font-medium">{job?.description || "Not specified"}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Address</dt>
            <dd className="font-medium">{job?.address || "Not specified"}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Customer</dt>
            <dd className="text-sm">{job?.customer_id?.slice(0, 8)}…</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Created</dt>
            <dd className="text-sm">
              {job?.created_at ? new Date(job.created_at).toLocaleString() : "—"}
            </dd>
          </div>
        </dl>
      </div>

      {(photos.length > 0 || audio.length > 0) && (
        <div className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="font-semibold text-foreground">Attached Media</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {photos.length > 0 && (
              <span className="rounded-full bg-primary/10 px-3 py-1 text-sm text-primary">
                {photos.length} photo{photos.length !== 1 ? "s" : ""}
              </span>
            )}
            {audio.length > 0 && (
              <span className="rounded-full bg-muted px-3 py-1 text-sm text-muted-foreground">
                {audio.length} voice note{audio.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="mt-6 space-y-4">
        <FutureFeature featureId="job_summary" />
        {audio.length > 0 && <FutureFeature featureId="voice_transcript" />}
      </div>

      <div className="mt-6">
        <Link
          href="/estimates"
          className="inline-flex text-sm font-medium text-primary hover:underline"
        >
          Create estimate manually →
        </Link>
      </div>
    </div>
  );
}
