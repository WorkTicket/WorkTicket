"use client";

import { hasPermission, type Permission } from "@/lib/permissions";
import { useCurrentUser } from "@/lib/hooks/use-user";

export function usePermissions() {
  const { data: user, isLoading } = useCurrentUser();
  const role = user?.role ?? "read_only";

  return {
    role,
    isLoading,
    can: (permission: Permission) => hasPermission(role, permission),
    user,
  };
}
