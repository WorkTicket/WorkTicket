export default function MaintenancePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-center">
      <h1 className="text-2xl font-bold text-foreground">We&apos;ll be right back</h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        WorkTicket is undergoing scheduled maintenance. Please check back shortly.
      </p>
    </div>
  );
}
