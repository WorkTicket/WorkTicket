import { vi } from "vitest";

(globalThis as any).__DEV__ = true;

vi.mock("@react-native-community/netinfo", () => {
  const mockNetInfo = {
    fetch: vi.fn().mockResolvedValue({ isConnected: true, isInternetReachable: true }),
    addEventListener: vi.fn(),
  };
  return {
    default: mockNetInfo,
  };
});
