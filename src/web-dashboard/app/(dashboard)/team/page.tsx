import { UsersRound } from "lucide-react";
import { ModuleScaffold } from "@/components/dashboard/module-scaffold";
import { PermissionGate } from "@/components/dashboard/permission-gate";

export default function TeamPage() {
  return (
    <PermissionGate permission="team:view">
      <ModuleScaffold
        title="Team"
        description="Manage roles, permissions, invitations, and activity logs."
        icon={UsersRound}
      />
    </PermissionGate>
  );
}
