"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";

interface RegistrationStatus {
  registered: boolean;
  user_id: string;
}

export function RegistrationGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isLoaded, isSignedIn } = useAuth();

  const { data, isLoading, isError } = useQuery<RegistrationStatus>({
    queryKey: ["registration-status"],
    queryFn: () => api.get("/auth/registration-status").then((r) => r.data),
    enabled: isLoaded && !!isSignedIn,
    retry: false,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!isLoaded || !isSignedIn || isLoading) return;
    if (data && !data.registered && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [isLoaded, isSignedIn, isLoading, data, pathname, router]);

  if (!isLoaded || (isSignedIn && isLoading)) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (isSignedIn && (isError || (data && !data.registered))) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return <>{children}</>;
}
