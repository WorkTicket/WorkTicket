"use client";

import { UserProfile } from "@clerk/nextjs";
import { PageHeader } from "@/components/dashboard/page-header";

export default function AccountSettingsPage() {
  return (
    <div>
      <PageHeader title="Account" description="Manage your profile, security, and active sessions." />
      <div className="max-w-2xl">
        <UserProfile routing="hash" />
      </div>
    </div>
  );
}
