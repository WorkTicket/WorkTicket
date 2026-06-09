import { Calendar } from "lucide-react";
import { ModuleScaffold } from "@/components/dashboard/module-scaffold";
import { PermissionGate } from "@/components/dashboard/permission-gate";

export default function SchedulingPage() {
  return (
    <PermissionGate permission="scheduling:view">
      <ModuleScaffold
        title="Scheduling"
        description="Calendar view with drag-and-drop scheduling and technician assignment."
        icon={Calendar}
      />
    </PermissionGate>
  );
}
