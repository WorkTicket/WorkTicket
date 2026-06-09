import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "WorkTicket privacy policy.",
};

export default function PrivacyPage() {
  return (
    <section className="section-padding">
      <div className="container-content mx-auto max-w-3xl prose-marketing">
        <h1>Privacy Policy</h1>
        <p className="text-sm text-slate-500">Last updated: June 1, 2026</p>
        <p>
          WorkTicket (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) respects your privacy. This policy
          describes how we collect, use, and protect information when you use our website and
          services.
        </p>
        <h2>Information We Collect</h2>
        <p>
          We collect information you provide directly, such as name, email, company name, and job
          data entered into the platform. We also collect usage analytics to improve our product.
        </p>
        <h2>How We Use Information</h2>
        <p>
          We use your information to provide and improve WorkTicket, process billing, send service
          communications, and ensure security of our multi-tenant platform.
        </p>
        <h2>Data Security</h2>
        <p>
          We implement industry-standard security measures including encryption, tenant isolation,
          and access controls. Data is never shared across organizations.
        </p>
        <h2>Contact</h2>
        <p>
          For privacy questions, contact us at{" "}
          <a href="mailto:privacy@workticket.app">privacy@workticket.app</a>.
        </p>
      </div>
    </section>
  );
}
