"use client";

import { OrganizationProfile } from "@clerk/nextjs";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";

export default function OrganizationSettingsPage() {
  return (
    <PermissionGate permission="settings:manage">
      <div>
        <PageHeader title="Organization" description="Company profile, branding, and team settings." />
        <div className="max-w-2xl">
          <OrganizationProfile routing="hash" />
        </div>
      </div>
    </PermissionGate>
  );
}
