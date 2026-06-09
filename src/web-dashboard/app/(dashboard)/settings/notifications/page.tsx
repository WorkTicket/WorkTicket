import { PageHeader } from "@/components/dashboard/page-header";

const notificationTypes = [
  { id: "job_assigned", label: "Job assigned", channels: ["in-app", "email"] },
  { id: "estimate_approved", label: "Estimate approved", channels: ["in-app", "email"] },
  { id: "new_comment", label: "New comment", channels: ["in-app"] },
  { id: "team_invitation", label: "Team invitation", channels: ["in-app", "email"] },
  { id: "billing_receipt", label: "Billing receipt", channels: ["email"] },
];

export default function NotificationsSettingsPage() {
  return (
    <div>
      <PageHeader title="Notifications" description="Choose how you receive updates." />
      <div className="space-y-3">
        {notificationTypes.map((item) => (
          <div key={item.id} className="flex items-center justify-between rounded-xl border border-border bg-card p-4">
            <div>
              <p className="font-medium text-foreground">{item.label}</p>
              <p className="text-xs text-muted-foreground">{item.channels.join(" · ")}</p>
            </div>
            <span className="text-xs text-muted-foreground">Enabled (v1 defaults)</span>
          </div>
        ))}
      </div>
    </div>
  );
}
