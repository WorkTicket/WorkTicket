import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "WorkTicket terms of service.",
};

export default function TermsPage() {
  return (
    <section className="section-padding">
      <div className="container-content mx-auto max-w-3xl prose-marketing">
        <h1>Terms of Service</h1>
        <p className="text-sm text-slate-500">Last updated: June 1, 2026</p>
        <p>
          By accessing or using WorkTicket, you agree to these Terms of Service. If you do not
          agree, do not use our services.
        </p>
        <h2>Service Description</h2>
        <p>
          WorkTicket provides job management software for skilled trades businesses, including web
          dashboard and mobile applications.
        </p>
        <h2>Account Responsibilities</h2>
        <p>
          You are responsible for maintaining the security of your account credentials and for all
          activity under your organization&apos;s account.
        </p>
        <h2>Subscription & Billing</h2>
        <p>
          Paid plans are billed monthly or annually as selected. You may cancel at any time; access
          continues through the end of the billing period.
        </p>
        <h2>Limitation of Liability</h2>
        <p>
          WorkTicket is provided &quot;as is&quot; to the maximum extent permitted by law. We are not
          liable for indirect or consequential damages arising from use of the service.
        </p>
        <h2>Contact</h2>
        <p>
          Questions about these terms:{" "}
          <a href="mailto:legal@workticket.app">legal@workticket.app</a>.
        </p>
      </div>
    </section>
  );
}
