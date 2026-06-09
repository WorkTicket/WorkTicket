import { CreditCard } from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";
import { FUTURE_FEATURE_LABEL } from "@/lib/product-rules";

export default function BillingPage() {
  return (
    <PermissionGate permission="billing:view">
      <div>
        <PageHeader
          title="Billing"
          description="Manage your subscription and payment history."
        />
        <div className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
          <CreditCard className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
          <h2 className="mt-4 text-lg font-semibold text-foreground">Upgrade plan</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Online billing and plan upgrades are {FUTURE_FEATURE_LABEL.toLowerCase()}. Your account
            is active on the current release — no payment action required.
          </p>
          <span className="mt-4 inline-flex rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-600/20">
            {FUTURE_FEATURE_LABEL}
          </span>
        </div>
      </div>
    </PermissionGate>
  );
}
