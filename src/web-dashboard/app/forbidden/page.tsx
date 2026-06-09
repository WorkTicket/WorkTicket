import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-center">
      <p className="text-sm font-semibold text-destructive">403</p>
      <h1 className="mt-2 text-2xl font-bold text-foreground">Access denied</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        You don&apos;t have permission to access this resource.
      </p>
      <Link href="/dashboard" className="mt-6">
        <Button>Return to Dashboard</Button>
      </Link>
    </div>
  );
}
