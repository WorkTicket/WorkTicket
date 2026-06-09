import { describe, it, expect, vi, beforeEach } from "vitest";

// Import analytics module statically
import {
  logEvent,
  EVENT_JOB_CREATED,
  EVENT_AI_OUTPUT_GENERATED,
  EVENT_AI_OUTPUT_VIEWED,
  EVENT_VOICE_USED,
  EVENT_PHOTO_UPLOADED,
  EVENT_OFFLINE_SYNC_COMPLETED,
} from "../utils/analytics";

// Mock the api client
vi.mock("../api/client", () => ({
  api: {
    post: vi.fn().mockResolvedValue({ data: { success: true } }),
  },
  setTokenGetter: vi.fn(),
  getUploadUrl: vi.fn(),
  confirmUpload: vi.fn(),
  fetchCustomers: vi.fn(),
  createCustomer: vi.fn(),
  registerPushToken: vi.fn(),
}));

// Mock network
vi.mock("../utils/network", () => ({
  isOnline: vi.fn().mockReturnValue(true),
}));

// Mock offline queue dependencies (needed by catch block imports)
vi.mock("expo-sqlite", () => ({
  openDatabaseAsync: vi.fn().mockResolvedValue({
    execAsync: vi.fn().mockResolvedValue(undefined),
    runAsync: vi.fn().mockResolvedValue({ lastInsertRowId: 1, changes: 1 }),
    getAllAsync: vi.fn().mockResolvedValue([]),
  }),
}));
vi.mock("expo-file-system", () => ({
  getInfoAsync: vi.fn().mockResolvedValue({ exists: true, size: 1024 }),
  documentDirectory: "/mock/documents/",
}));

// Mock auth store
vi.mock("../stores/authStore", () => ({
  useAuthStore: {
    getState: vi.fn().mockReturnValue({
      userId: "user-1",
      companyId: "company-1",
    }),
  },
}));

describe("Analytics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should define all event constants", () => {
    expect(EVENT_JOB_CREATED).toBe("job_created");
    expect(EVENT_AI_OUTPUT_GENERATED).toBe("ai_output_generated");
    expect(EVENT_AI_OUTPUT_VIEWED).toBe("ai_output_viewed");
    expect(EVENT_VOICE_USED).toBe("voice_used");
    expect(EVENT_PHOTO_UPLOADED).toBe("photo_uploaded");
    expect(EVENT_OFFLINE_SYNC_COMPLETED).toBe("offline_sync_completed");
  });

  it("should log events without throwing", async () => {
    await expect(
      logEvent(EVENT_JOB_CREATED, "job-1")
    ).resolves.not.toThrow();
  });

  it("should handle API failure gracefully", async () => {
    const { api } = await import("../api/client");
    (api.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));

    await expect(
      logEvent(EVENT_JOB_CREATED, "job-1")
    ).resolves.not.toThrow();

    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { success: true } });
  });
});
