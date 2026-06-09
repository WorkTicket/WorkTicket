import Link from "next/link";
import { Settings, Plug } from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";

const settingsLinks = [
  { href: "/settings/integrations", label: "Integrations", description: "Connect QuickBooks, Jobber, Stripe, and more", icon: Plug },
  { href: "/settings/account", label: "Account", description: "Profile, security, and sessions" },
  { href: "/settings/organization", label: "Organization", description: "Company profile and branding" },
  { href: "/settings/notifications", label: "Notifications", description: "Email and in-app preferences" },
  { href: "/support", label: "Support", description: "Help center and contact support" },
];

export default function SettingsPage() {
  return (
    <PermissionGate permission="settings:view">
      <div>
        <PageHeader title="Settings" description="Manage your account and organization." />
        <div className="grid gap-4 sm:grid-cols-2">
          {settingsLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-start gap-3">
                {link.icon ? <link.icon className="mt-0.5 h-5 w-5 text-muted-foreground" /> : <Settings className="mt-0.5 h-5 w-5 text-muted-foreground" />}
                <div>
                  <p className="font-medium text-foreground">{link.label}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{link.description}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </PermissionGate>
  );
}
