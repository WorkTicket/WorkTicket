import Link from "next/link";
import { PageHeader } from "@/components/dashboard/page-header";

export default function SupportPage() {
  return (
    <div>
      <PageHeader title="Support" description="Get help with WorkTicket." />
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="font-semibold">Help Center</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Browse guides for jobs, estimates, scheduling, and team management.
          </p>
          <Link href="#" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
            View documentation →
          </Link>
        </div>
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="font-semibold">Contact Support</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Email our team and we&apos;ll respond within one business day.
          </p>
          <a href="mailto:support@workticket.app" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
            support@workticket.app
          </a>
        </div>
        <div className="rounded-xl border border-border bg-card p-6 sm:col-span-2">
          <h2 className="font-semibold">Report an Issue</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Describe the problem you encountered, including steps to reproduce if possible.
          </p>
          <a href="mailto:support@workticket.app?subject=Issue%20Report" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
            Report issue →
          </a>
        </div>
      </div>
    </div>
  );
}
