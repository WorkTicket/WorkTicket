import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import * as SecureStore from "expo-secure-store";

const secureStorage = {
  getItem: async (name: string) => {
    try {
      return await SecureStore.getItemAsync(name, {
        authenticationPrompt: "Authenticate to access account",
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        requireAuthentication: false,
      });
    } catch (err) {
      console.error("SecureStore getItem failed:", err);
      try {
        return await SecureStore.getItemAsync(name);
      } catch {
        return null;
      }
    }
  },
  setItem: async (name: string, value: string) => {
    try {
      await SecureStore.setItemAsync(name, value, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        authenticationPrompt: "Authenticate to save account credentials",
        requireAuthentication: true,
      });
    } catch (err) {
      console.error("SecureStore setItem failed:", err);
      try {
        await SecureStore.setItemAsync(name, value);
      } catch {}
    }
  },
  removeItem: async (name: string) => {
    try {
      await SecureStore.deleteItemAsync(name);
    } catch (err) {
      console.error("SecureStore deleteItem failed:", err);
    }
  },
};

interface AuthState {
  userId: string | null;
  companyId: string | null;
  role: string | null;
  token: string | null;
  setAuth: (auth: { userId: string; companyId: string; role: string; token: string }) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: null,
      companyId: null,
      role: null,
      token: null,
      setAuth: (auth) => set({ ...auth }),
      clearAuth: () => set({ userId: null, companyId: null, role: null, token: null }),
    }),
    {
      name: "workticket-auth",
      storage: createJSONStorage(() => secureStorage),
    }
  )
);