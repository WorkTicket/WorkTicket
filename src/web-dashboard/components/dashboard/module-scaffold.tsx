import { type LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { EmptyState } from "@/components/dashboard/empty-state";

interface ModuleScaffoldProps {
  title: string;
  description: string;
  icon: LucideIcon;
}

export function ModuleScaffold({ title, description, icon }: ModuleScaffoldProps) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={icon}
        title={`${title} module`}
        description="This module is wired into the dashboard navigation and permissions system. Connect your backend APIs to populate this view."
      />
    </div>
  );
}
