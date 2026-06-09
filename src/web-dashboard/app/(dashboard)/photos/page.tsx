import { Camera } from "lucide-react";
import { ModuleScaffold } from "@/components/dashboard/module-scaffold";
import { PermissionGate } from "@/components/dashboard/permission-gate";

export default function PhotosPage() {
  return (
    <PermissionGate permission="media:view">
      <ModuleScaffold
        title="Photos"
        description="Upload, categorize, and associate photos with jobs."
        icon={Camera}
      />
    </PermissionGate>
  );
}
