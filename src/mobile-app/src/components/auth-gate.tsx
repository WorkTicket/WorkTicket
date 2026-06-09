import { useCallback, useEffect, useState } from "react";
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useAuth, useUser } from "@clerk/clerk-expo";
import { fetchRegistrationStatus, registerUser } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

type GateState = "loading" | "unregistered" | "ready" | "error";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth();
  const { user, isLoaded } = useUser();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [gateState, setGateState] = useState<GateState>("loading");
  const [companyName, setCompanyName] = useState("");
  const [registering, setRegistering] = useState(false);

  const syncRegisteredUser = useCallback(async () => {
    const status = await fetchRegistrationStatus();
    if (!status.registered || !status.company_id || !status.role) {
      setGateState("unregistered");
      return;
    }
    const token = (await getToken()) ?? "";
    setAuth({
      userId: status.user_id,
      companyId: status.company_id,
      role: status.role,
      token,
    });
    setGateState("ready");
  }, [getToken, setAuth]);

  useEffect(() => {
    if (!isLoaded || !user) return;
    syncRegisteredUser().catch(() => setGateState("error"));
  }, [isLoaded, user, syncRegisteredUser]);

  const handleRegister = useCallback(async () => {
    if (!user || !companyName.trim() || registering) return;
    setRegistering(true);
    try {
      const result = await registerUser({
        user_id: user.id,
        email: user.primaryEmailAddress?.emailAddress ?? "",
        name: user.fullName ?? user.firstName ?? "User",
        company_name: companyName.trim(),
      });
      const token = (await getToken()) ?? "";
      setAuth({
        userId: result.user_id,
        companyId: result.company_id,
        role: result.role,
        token,
      });
      setGateState("ready");
    } catch {
      Alert.alert(
        "Registration failed",
        "Could not create your company account. The name may already exist — try a different name."
      );
    } finally {
      setRegistering(false);
    }
  }, [user, companyName, registering, getToken, setAuth]);

  if (gateState === "error") {
    return (
      <View className="flex-1 justify-center items-center bg-gray-50 p-6">
        <Text className="text-red-600 text-center mb-4">Could not verify your account. Check your connection.</Text>
        <TouchableOpacity
          className="bg-blue-600 px-6 py-3 rounded-lg"
          onPress={() => {
            setGateState("loading");
            syncRegisteredUser().catch(() => setGateState("error"));
          }}
          accessibilityLabel="Retry"
          accessibilityRole="button"
        >
          <Text className="text-white font-semibold">Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!isLoaded || gateState === "loading") {
    return (
      <View className="flex-1 justify-center items-center bg-gray-50">
        <ActivityIndicator size="large" accessibilityLabel="Loading account" />
      </View>
    );
  }

  if (gateState === "unregistered") {
    return (
      <View className="flex-1 justify-center bg-gray-50 p-6">
        <Text className="text-2xl font-bold mb-2">Set up your company</Text>
        <Text className="text-gray-500 mb-6">
          Create your WorkTicket organization to start managing jobs.
        </Text>
        <Text className="text-sm font-medium text-gray-700 mb-1">Company name</Text>
        <TextInput
          className="bg-white border border-gray-300 rounded-lg px-4 py-3 mb-4"
          value={companyName}
          onChangeText={setCompanyName}
          placeholder="ABC Plumbing"
          autoCapitalize="words"
          accessibilityLabel="Company name"
        />
        <TouchableOpacity
          className="bg-blue-600 py-3 rounded-lg items-center"
          onPress={handleRegister}
          disabled={registering || companyName.trim().length < 2}
          accessibilityLabel="Create company"
          accessibilityRole="button"
        >
          {registering ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text className="text-white font-semibold">Create Company</Text>
          )}
        </TouchableOpacity>
      </View>
    );
  }

  return <>{children}</>;
}
