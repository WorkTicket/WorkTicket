import { api } from "./api";

export const EVENT_JOB_CREATED = "job_created";
export const EVENT_AI_OUTPUT_GENERATED = "ai_output_generated";
export const EVENT_AI_OUTPUT_VIEWED = "ai_output_viewed";
export const EVENT_AI_OUTPUT_EDITED = "ai_output_edited";
export const EVENT_JOB_APPROVED_WITHOUT_CHANGES = "job_approved_without_changes";
export const EVENT_JOB_APPROVED_WITH_CHANGES = "job_approved_with_changes";
export const EVENT_JOB_SENT = "job_sent";
export const EVENT_JOB_REOPENED = "job_reopened";
export const EVENT_VOICE_USED = "voice_used";
export const EVENT_PHOTO_UPLOADED = "photo_uploaded";
export const EVENT_OFFLINE_SYNC_COMPLETED = "offline_sync_completed";

const STORAGE_KEY = "workticket-analytics-queue";

type PendingEvent = {
  event_name: string;
  job_id?: string;
  client_timestamp: string;
  metadata: Record<string, unknown>;
};

function loadQueue(): PendingEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    if (process.env.NODE_ENV !== "production") {
      console.error("Failed to parse analytics queue from localStorage:", e);
    }
    return [];
  }
}

function saveQueue(events: PendingEvent[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
  } catch (e) {
    if (process.env.NODE_ENV !== "production") {
      console.error("Failed to save analytics queue to localStorage:", e);
    }
  }
}

const pendingEvents: PendingEvent[] = loadQueue();

export async function logEvent(
  eventName: string,
  jobId?: string,
  metadata?: Record<string, unknown>,
) {
  const payload: PendingEvent = {
    event_name: eventName,
    job_id: jobId,
    client_timestamp: new Date().toISOString(),
    metadata: metadata || {},
  };
  try {
    await api.post("/analytics/events", payload);
  } catch (e) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("Analytics event failed, queued for retry:", eventName, e);
    }
    pendingEvents.push(payload);
    saveQueue(pendingEvents);
    if (pendingEvents.length >= 10) {
      flushPendingEvents();
    }
  }
}

async function flushPendingEvents() {
  if (pendingEvents.length === 0) return;
  const batch = pendingEvents.splice(0);
  saveQueue(pendingEvents);
  for (const event of batch) {
    try {
      await api.post("/analytics/events", event);
    } catch (e) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Analytics event permanently failed:", event.event_name, e);
      }
    }
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    if (pendingEvents.length > 0) {
      navigator.sendBeacon?.(
        `${api.defaults.baseURL}/analytics/events`,
        JSON.stringify(pendingEvents),
      );
    }
  });
}
