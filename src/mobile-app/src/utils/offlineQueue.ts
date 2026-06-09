import * as SQLite from "expo-sqlite";
import * as FileSystem from "expo-file-system";
import { getUploadUrl, confirmUpload } from "@/api/client";
import { isOnline } from "@/utils/network";

interface UploadQueueRow {
  id: number;
  client_media_id: string | null;
  job_id: string;
  file_uri: string;
  content_type: string;
  status: string;
  retry_count: number;
  created_at: string;
  last_error: string | null;
}

interface AnalyticsQueueRow {
  id: number;
  event_name: string;
  user_id: string;
  company_id: string;
  job_id: string | null;
  client_timestamp: string;
  metadata_json: string | null;
  status: string;
  retry_count: number;
  created_at: string;
}

let db: SQLite.SQLiteDatabase;
let initPromise: Promise<void> | null = null;

export async function initQueue() {
  if (initPromise) return initPromise;
  _totalReplayCount = 0;
  initPromise = (async () => {
    db = await SQLite.openDatabaseAsync("workticket-offline.db");
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS upload_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_media_id TEXT,
        job_id TEXT NOT NULL,
        file_uri TEXT NOT NULL,
        content_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        last_error TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
    `);
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS analytics_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        company_id TEXT NOT NULL,
        job_id TEXT,
        client_timestamp TEXT NOT NULL,
        metadata_json TEXT,
        status TEXT DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        last_error TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
    `);
  })();
  return initPromise;
}

async function ensureDb() {
  if (!db) await initQueue();
}

function generateUUID(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export async function enqueueUpload(jobId: string, fileUri: string, contentType: string): Promise<string> {
  await ensureDb();
  const clientMediaId = generateUUID();
  await db.runAsync(
    "INSERT INTO upload_queue (client_media_id, job_id, file_uri, content_type) VALUES (?, ?, ?, ?)",
    clientMediaId,
    jobId,
    fileUri,
    contentType
  );
  return clientMediaId;
}

export async function updateQueueJobId(oldJobId: string, newJobId: string) {
  await ensureDb();
  await db.runAsync(
    "UPDATE upload_queue SET job_id = ? WHERE job_id = ? AND status = 'pending'",
    newJobId,
    oldJobId
  );
}

export async function getPendingUploads() {
  await ensureDb();
  const rows = await db.getAllAsync(
    "SELECT * FROM upload_queue WHERE status = 'pending' AND retry_count < 3 ORDER BY created_at ASC"
  );
  return rows as UploadQueueRow[];
}

export async function markComplete(id: number) {
  await ensureDb();
  await db.runAsync("UPDATE upload_queue SET status = 'completed' WHERE id = ?", id);
}

export async function markFailed(id: number, error: string) {
  await ensureDb();
  await db.runAsync(
    "UPDATE upload_queue SET retry_count = retry_count + 1, last_error = ?, status = CASE WHEN retry_count + 1 >= 3 THEN 'failed' ELSE 'pending' END WHERE id = ?",
    error,
    id
  );
}

export const MAX_CONCURRENT_UPLOADS = 3;
export const MAX_RETRIES = 3;
export const MAX_TOTAL_REPLAYS = 50;
let _totalReplayCount = 0;

async function uploadSingle(item: UploadQueueRow): Promise<{ id: number; success: boolean; error?: string }> {
  try {
    const info = await FileSystem.getInfoAsync(item.file_uri);
    if (!info.exists) {
      await markFailed(item.id, "File not found");
      return { id: item.id, success: false, error: "File not found" };
    }

    const ext = item.content_type === "image/jpeg" ? "jpg" : "m4a";
    const upload = await getUploadUrl({
      job_id: item.job_id,
      file_name: `offline-${item.client_media_id || item.id}.${ext}`,
      content_type: item.content_type,
      file_size: info.size || 0,
      client_media_id: item.client_media_id || undefined,
    });

    await FileSystem.uploadAsync(upload.upload_url, item.file_uri, {
      fieldName: "file",
      httpMethod: "PUT",
      uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
    });

    await confirmUpload(upload.media_id);
    await markComplete(item.id);
    return { id: item.id, success: true };
  } catch (e: unknown) {
    const errorMsg = (e as { message?: string })?.message || "Upload failed";
    await markFailed(item.id, errorMsg);
    return { id: item.id, success: false, error: errorMsg };
  }
}

export async function enqueueAnalyticsEvent(
  eventName: string,
  userId: string,
  companyId: string,
  jobId?: string,
  metadata?: Record<string, unknown>,
) {
  await ensureDb();
  const clientTimestamp = new Date().toISOString();
  await db.runAsync(
    `INSERT INTO analytics_queue (event_name, user_id, company_id, job_id, client_timestamp, metadata_json)
     VALUES (?, ?, ?, ?, ?, ?)`,
    eventName,
    userId,
    companyId,
    jobId || null,
    clientTimestamp,
    metadata ? JSON.stringify(metadata) : null,
  );
}

export async function getPendingAnalyticsEvents() {
  await ensureDb();
  const rows = await db.getAllAsync(
    "SELECT * FROM analytics_queue WHERE status = 'pending' AND retry_count < 3 ORDER BY created_at ASC"
  );
  return rows as AnalyticsQueueRow[];
}

async function markAnalyticsComplete(id: number) {
  await ensureDb();
  await db.runAsync("UPDATE analytics_queue SET status = 'completed' WHERE id = ?", id);
}

async function markAnalyticsFailed(id: number, error: string) {
  await ensureDb();
  await db.runAsync(
    `UPDATE analytics_queue SET retry_count = retry_count + 1, last_error = ?,
     status = CASE WHEN retry_count + 1 >= 3 THEN 'failed' ELSE 'pending' END WHERE id = ?`,
    error,
    id,
  );
}

export async function processAnalyticsQueue() {
  const pending = await getPendingAnalyticsEvents();
  if (pending.length === 0) return [];

  const { api } = await import("@/api/client");
  const results: { id: number; success: boolean; error?: string }[] = [];

  for (const event of pending) {
    try {
      await api.post("/analytics/events", {
        event_name: event.event_name,
        user_id: event.user_id,
        company_id: event.company_id,
        job_id: event.job_id || undefined,
        client_timestamp: event.client_timestamp,
        metadata: event.metadata_json ? JSON.parse(event.metadata_json) : {},
      });
      await markAnalyticsComplete(event.id);
      results.push({ id: event.id, success: true });
    } catch (e: unknown) {
      const errorMsg = (e as { message?: string })?.message || "Sync failed";
      await markAnalyticsFailed(event.id, errorMsg);
      results.push({ id: event.id, success: false, error: errorMsg });
    }
  }

  return results;
}

export async function processQueue() {
  if (!isOnline()) {
    return { uploads: [], analytics: [], conflicts: [] };
  }
  if (_totalReplayCount >= MAX_TOTAL_REPLAYS) {
    if (__DEV__) console.warn("Offline queue replay limit reached — dropping processQueue call");
    return { uploads: [], analytics: [], conflicts: [] };
  }

  // Check if user is still authenticated before processing queue
  try {
    const { useAuthStore } = await import("@/stores/authStore");
    const { userId, token } = useAuthStore.getState();
    if (!userId || !token) {
      if (__DEV__) console.warn("User not authenticated — skipping offline queue processing");
      return { uploads: [], analytics: [], conflicts: [] };
    }
  } catch (error) {
    if (__DEV__) console.error("Failed to check authentication status:", error);
  }

  const pending = await getPendingUploads();
  const uploadResults: { id: number; success: boolean; error?: string }[] = [];
  const conflicts: { id: number; resource: string; serverVersion: string; localVersion: string }[] = [];

  for (let i = 0; i < pending.length; i += MAX_CONCURRENT_UPLOADS) {
    const batch = pending.slice(i, i + MAX_CONCURRENT_UPLOADS);
    const results = await Promise.allSettled(batch.map(uploadSingle));
    for (const r of results) {
      if (r.status === "fulfilled") {
        uploadResults.push(r.value);
        if (r.value.error?.includes("412") || r.value.error?.includes("Precondition Failed")) {
          conflicts.push({
            id: r.value.id,
            resource: "upload",
            serverVersion: "unknown",
            localVersion: "local",
          });
        }
      }
    }
  }

  const analyticsResults = await processAnalyticsQueue();

  _totalReplayCount++

  if (uploadResults.length > 0 || analyticsResults.length > 0 || conflicts.length > 0) {
    const { logEvent, EVENT_OFFLINE_SYNC_COMPLETED } = await import("@/utils/analytics");
    logEvent(EVENT_OFFLINE_SYNC_COMPLETED, undefined, {
      uploads: { total: uploadResults.length, success_count: uploadResults.filter((r) => r.success).length, failed_count: uploadResults.filter((r) => !r.success).length },
      analytics: { total: analyticsResults.length, success_count: analyticsResults.filter((r) => r.success).length, failed_count: analyticsResults.filter((r) => !r.success).length },
      conflicts: conflicts.length,
    }).catch(console.error);
  }

  if (conflicts.length > 0) {
    if (__DEV__) console.warn("Offline queue conflicts detected:", conflicts);
  }

  return { uploads: uploadResults, analytics: analyticsResults, conflicts };
}