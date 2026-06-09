import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "Learn about WorkTicket and our mission to simplify job management for skilled trades.",
};

export default function AboutPage() {
  return (
    <section className="section-padding">
      <div className="container-content mx-auto max-w-3xl">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">About WorkTicket</h1>
        <div className="prose-marketing mt-8 space-y-6 text-slate-600">
          <p>
            WorkTicket was built for contractors who are tired of juggling spreadsheets, text
            messages, and disconnected tools. We believe skilled trades businesses deserve
            software that is as reliable and straightforward as the work they do every day.
          </p>
          <p>
            Our platform brings together customers, jobs, estimates, scheduling, photos, and team
            management in one place — with a mobile app designed specifically for field
            technicians.
          </p>
          <h2 className="text-2xl font-semibold text-slate-900">Our values</h2>
          <ul className="list-disc space-y-2 pl-5">
            <li>Simplicity over complexity — your customers are contractors, not designers.</li>
            <li>Speed matters — fast loading, mobile-first, accessible by default.</li>
            <li>Trust through security — multi-tenant isolation and role-based permissions.</li>
            <li>Manual-first workflows — optional enhancements planned for future updates, never required today.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
