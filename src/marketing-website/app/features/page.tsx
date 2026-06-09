import type { Metadata } from "next";
import { CtaSection } from "@/components/marketing/cta-section";
import { FeatureGrid } from "@/components/marketing/feature-grid";

export const metadata: Metadata = {
  title: "Features",
  description: "Explore WorkTicket features for job management, estimates, scheduling, and field teams.",
};

const detailedFeatures = [
  {
    title: "Customer Directory",
    items: ["Search and filter customers", "Contact information and notes", "Complete job history"],
  },
  {
    title: "Job Lifecycle",
    items: ["Lead through closed statuses", "Photos and attachments", "Activity timeline"],
  },
  {
    title: "Estimates",
    items: ["Line items with tax and discounts", "PDF export", "Customer approval workflow"],
  },
  {
    title: "Billing & Subscriptions",
    items: ["Plan management", "Payment history", "Usage tracking"],
  },
];

export default function FeaturesPage() {
  return (
    <>
      <section className="section-padding bg-surface-muted">
        <div className="container-content">
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="text-4xl font-bold tracking-tight text-slate-900">Features</h1>
            <p className="mt-4 text-lg text-slate-600">
              Professional tools designed for contractors — not designers. Clean, fast, and easy
              for your whole team to use.
            </p>
          </div>
          <div className="mt-12">
            <FeatureGrid />
          </div>
        </div>
      </section>

      <section className="section-padding">
        <div className="container-content grid gap-8 md:grid-cols-2">
          {detailedFeatures.map((section) => (
            <div key={section.title} className="rounded-2xl border border-surface-border p-8">
              <h2 className="text-xl font-semibold text-slate-900">{section.title}</h2>
              <ul className="mt-4 space-y-2">
                {section.items.map((item) => (
                  <li key={item} className="flex items-center gap-2 text-slate-600">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-600" aria-hidden />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <CtaSection />
    </>
  );
}
