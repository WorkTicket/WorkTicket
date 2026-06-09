import type { Metadata } from "next";
import { CtaSection } from "@/components/marketing/cta-section";
import { FeatureGrid } from "@/components/marketing/feature-grid";
import { Hero } from "@/components/marketing/hero";

export const metadata: Metadata = {
  title: "Job Management for Skilled Trades",
  description:
    "Manage customers, jobs, estimates, scheduling, and field teams with WorkTicket — built for contractors.",
};

export default function HomePage() {
  return (
    <>
      <Hero />
      <section className="section-padding border-t border-surface-border bg-white" aria-labelledby="features-heading">
        <div className="container-content">
          <div className="mx-auto max-w-2xl text-center">
            <h2 id="features-heading" className="text-3xl font-bold tracking-tight text-slate-900">
              Everything your team needs on the job
            </h2>
            <p className="mt-4 text-slate-600">
              From the office to the job site — one platform for your entire workflow.
            </p>
          </div>
          <div className="mt-12">
            <FeatureGrid />
          </div>
        </div>
      </section>
      <CtaSection />
    </>
  );
}
