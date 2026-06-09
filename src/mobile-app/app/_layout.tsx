import { useEffect } from "react";
import { Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider, SignedIn, SignedOut, useAuth } from "@clerk/clerk-expo";
import { StatusBar } from "expo-status-bar";
import { AuthGate } from "@/components/auth-gate";
import { ErrorBoundary } from "@/components/error-boundary";
import { setTokenGetter } from "@/api/client";
import "@/global.css";

const queryClient = new QueryClient();

function TokenProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth();

  useEffect(() => {
    setTokenGetter(getToken);
  }, [getToken]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <ErrorBoundary>
      <ClerkProvider publishableKey={process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY!}>
        <QueryClientProvider client={queryClient}>
          <TokenProvider>
            <StatusBar style="auto" />
            <SignedIn>
              <AuthGate>
                <Stack screenOptions={{ headerShown: false }}>
                  <Stack.Screen name="(tabs)" />
                  <Stack.Screen name="job/[id]" />
                </Stack>
              </AuthGate>
            </SignedIn>
            <SignedOut>
              <Stack screenOptions={{ headerShown: false }}>
                <Stack.Screen name="login" />
              </Stack>
            </SignedOut>
          </TokenProvider>
        </QueryClientProvider>
      </ClerkProvider>
    </ErrorBoundary>
  );
}
