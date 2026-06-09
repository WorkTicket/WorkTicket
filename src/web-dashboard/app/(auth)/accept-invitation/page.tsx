import { SignUp } from "@clerk/nextjs";

export default function AcceptInvitationPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-foreground">Accept your invitation</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Create your account or sign in to join your team on WorkTicket.
        </p>
      </div>
      <SignUp routing="path" path="/accept-invitation" signInUrl="/sign-in" forceRedirectUrl="/dashboard" />
    </div>
  );
}
