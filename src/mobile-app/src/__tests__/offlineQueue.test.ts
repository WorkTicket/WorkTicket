import { describe, it, expect, vi, beforeEach } from "vitest";

// Imports after mocks for vitest hoisting compatibility
import {
  initQueue,
  enqueueUpload,
  processQueue,
  MAX_RETRIES,
  MAX_CONCURRENT_UPLOADS,
} from "../utils/offlineQueue";

// Mock expo-sqlite
vi.mock("expo-sqlite", () => ({
  openDatabaseAsync: vi.fn().mockResolvedValue({
    execAsync: vi.fn().mockResolvedValue(undefined),
    runAsync: vi.fn().mockResolvedValue({ lastInsertRowId: 1, changes: 1 }),
    getAllAsync: vi.fn().mockResolvedValue([]),
  }),
}));

// Mock expo-file-system
vi.mock("expo-file-system", () => ({
  getInfoAsync: vi.fn().mockResolvedValue({ exists: true, size: 1024 }),
  documentDirectory: "/mock/documents/",
}));

// Mock API client
vi.mock("@/api/client", () => ({
  getUploadUrl: vi.fn().mockResolvedValue({
    upload_url: "https://example.com/upload",
    media_id: "media-1",
  }),
  confirmUpload: vi.fn().mockResolvedValue({ success: true }),
}));

// Mock network
vi.mock("@/utils/network", () => ({
  isOnline: vi.fn().mockReturnValue(true),
}));

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe("OfflineQueue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize database tables", async () => {
    const result = await initQueue();
    expect(result).toBeUndefined();
  });

  it("should enqueue upload items", async () => {
    await initQueue();
    const id = await enqueueUpload("job-1", "/tmp/photo.jpg", "image/jpeg");
    expect(id).toBeTruthy();
    expect(typeof id).toBe("string");
  });

  it("should have max retry limit of 3", () => {
    expect(MAX_RETRIES).toBe(3);
  });

  it("should have max concurrent uploads of 3", () => {
    expect(MAX_CONCURRENT_UPLOADS).toBe(3);
  });

  it("should handle empty queue processing gracefully", async () => {
    const result = await processQueue();
    expect(result).toEqual({ uploads: [], analytics: [], conflicts: [] });
  });
});
