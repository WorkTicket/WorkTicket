import { ButtonLink } from "@/components/ui/button";
import { signUpUrl } from "@/lib/utils";

export function CtaSection() {
  return (
    <section className="section-padding bg-brand-900 text-white">
      <div className="container-content text-center">
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Ready to simplify your job workflow?
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-brand-100">
          Join skilled trades businesses using WorkTicket to manage customers, jobs, and teams
          from one dashboard.
        </p>
        <div className="mt-8">
          <ButtonLink
            href={signUpUrl()}
            size="lg"
            className="bg-white text-brand-900 hover:bg-brand-50"
          >
            Start Your Free Trial
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
