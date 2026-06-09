"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api, setTokenGetter } from "@/lib/api";
import { normalizeRole, type UserRole } from "@/lib/permissions";
import { useEffect } from "react";

export interface CurrentUser {
  user_id: string;
  email: string;
  name: string;
  role: UserRole;
  company_id: string;
}

export function useCurrentUser() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  useEffect(() => {
    setTokenGetter(getToken);
  }, [getToken]);

  return useQuery({
    queryKey: ["current-user"],
    queryFn: async (): Promise<CurrentUser> => {
      const res = await api.get("/auth/me");
      const data = res.data as Omit<CurrentUser, "role"> & { role: string };
      return { ...data, role: normalizeRole(data.role) };
    },
    enabled: isLoaded && !!isSignedIn,
    staleTime: 60_000,
  });
}
