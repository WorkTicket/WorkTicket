"use client";

import Link from "next/link";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { type Permission } from "@/lib/permissions";
import { Spinner } from "@/components/ui/spinner";

interface PermissionGateProps {
  permission: Permission;
  children: React.ReactNode;
}

export function PermissionGate({ permission, children }: PermissionGateProps) {
  const { can, isLoading } = usePermissions();

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (!can(permission)) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-border bg-card p-8 text-center">
        <h2 className="text-xl font-semibold text-foreground">Access denied</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          You don&apos;t have permission to view this page. Contact your organization owner if you
          need access.
        </p>
        <Link href="/dashboard" className="mt-6 inline-block text-sm font-medium text-primary hover:underline">
          Return to dashboard
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
