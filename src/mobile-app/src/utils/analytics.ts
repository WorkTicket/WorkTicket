import { useAuthStore } from "@/stores/authStore";
import { api } from "@/api/client";
import { isOnline } from "@/utils/network";

const EVENT_JOB_CREATED = "job_created";
const EVENT_AI_OUTPUT_GENERATED = "ai_output_generated";
const EVENT_AI_OUTPUT_VIEWED = "ai_output_viewed";
const EVENT_AI_OUTPUT_EDITED = "ai_output_edited";
const EVENT_JOB_APPROVED_WITHOUT_CHANGES = "job_approved_without_changes";
const EVENT_JOB_APPROVED_WITH_CHANGES = "job_approved_with_changes";
const EVENT_JOB_SENT = "job_sent";
const EVENT_JOB_REOPENED = "job_reopened";
const EVENT_VOICE_USED = "voice_used";
const EVENT_PHOTO_UPLOADED = "photo_uploaded";
const EVENT_OFFLINE_SYNC_COMPLETED = "offline_sync_completed";

export async function logEvent(
  eventName: string,
  jobId?: string,
  metadata?: Record<string, unknown>,
) {
  const { userId, companyId } = useAuthStore.getState();
  if (!userId || !companyId) return;

  if (!isOnline()) {
    const { enqueueAnalyticsEvent } = await import("@/utils/offlineQueue");
    await enqueueAnalyticsEvent(eventName, userId, companyId, jobId, metadata);
    return;
  }

  try {
    await api.post("/analytics/events", {
      event_name: eventName,
      user_id: userId,
      company_id: companyId,
      job_id: jobId,
      client_timestamp: new Date().toISOString(),
      metadata: metadata || {},
    });
  } catch (err) {
    console.error("Failed to log analytics event:", err);
    const { enqueueAnalyticsEvent } = await import("@/utils/offlineQueue");
    await enqueueAnalyticsEvent(eventName, userId, companyId, jobId, metadata);
  }
}

export {
  EVENT_JOB_CREATED,
  EVENT_AI_OUTPUT_GENERATED,
  EVENT_AI_OUTPUT_VIEWED,
  EVENT_AI_OUTPUT_EDITED,
  EVENT_JOB_APPROVED_WITHOUT_CHANGES,
  EVENT_JOB_APPROVED_WITH_CHANGES,
  EVENT_JOB_SENT,
  EVENT_JOB_REOPENED,
  EVENT_VOICE_USED,
  EVENT_PHOTO_UPLOADED,
  EVENT_OFFLINE_SYNC_COMPLETED,
};
