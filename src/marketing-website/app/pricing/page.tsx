import type { Metadata } from "next";
import { Check } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { CtaSection } from "@/components/marketing/cta-section";
import { signUpUrl } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Simple, transparent pricing for skilled trades businesses of every size.",
};

const plans = [
  {
    name: "Starter",
    price: "$49",
    period: "/month",
    description: "For small crews getting organized.",
    features: ["Up to 3 team members", "Unlimited jobs & customers", "Mobile app access", "Email support"],
    highlighted: false,
  },
  {
    name: "Professional",
    price: "$99",
    period: "/month",
    description: "For growing businesses with multiple technicians.",
    features: [
      "Up to 15 team members",
      "Estimates & PDF export",
      "Scheduling & calendar",
      "Priority support",
    ],
    highlighted: true,
  },
  {
    name: "Business",
    price: "$199",
    period: "/month",
    description: "For established companies with advanced needs.",
    features: [
      "Unlimited team members",
      "Advanced permissions",
      "Usage analytics",
      "Dedicated onboarding",
    ],
    highlighted: false,
  },
];

export default function PricingPage() {
  return (
    <>
      <section className="section-padding bg-surface-muted">
        <div className="container-content">
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="text-4xl font-bold tracking-tight text-slate-900">Simple pricing</h1>
            <p className="mt-4 text-lg text-slate-600">
              No hidden fees. Choose the plan that fits your team and scale as you grow.
            </p>
          </div>

          <div className="mt-12 grid gap-8 lg:grid-cols-3">
            {plans.map((plan) => (
              <article
                key={plan.name}
                className={`flex flex-col rounded-2xl border p-8 ${
                  plan.highlighted
                    ? "border-brand-600 bg-white shadow-lg ring-2 ring-brand-600"
                    : "border-surface-border bg-white shadow-sm"
                }`}
              >
                {plan.highlighted && (
                  <span className="mb-4 inline-flex w-fit rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
                    Most Popular
                  </span>
                )}
                <h2 className="text-xl font-semibold text-slate-900">{plan.name}</h2>
                <p className="mt-2 text-sm text-slate-600">{plan.description}</p>
                <p className="mt-6">
                  <span className="text-4xl font-bold text-slate-900">{plan.price}</span>
                  <span className="text-slate-500">{plan.period}</span>
                </p>
                <ul className="mt-8 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm text-slate-600">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden />
                      {feature}
                    </li>
                  ))}
                </ul>
                <ButtonLink
                  href={signUpUrl()}
                  variant={plan.highlighted ? "primary" : "secondary"}
                  className="mt-8 w-full"
                >
                  Start Free Trial
                </ButtonLink>
              </article>
            ))}
          </div>
        </div>
      </section>
      <CtaSection />
    </>
  );
}
