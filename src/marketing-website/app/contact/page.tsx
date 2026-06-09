"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitted(true);
  }

  return (
    <section className="section-padding bg-surface-muted">
      <div className="container-content mx-auto max-w-xl">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">Contact us</h1>
        <p className="mt-4 text-slate-600">
          Have questions about WorkTicket? We&apos;d love to hear from you.
        </p>

        {submitted ? (
          <div
            role="status"
            className="mt-8 rounded-2xl border border-green-200 bg-green-50 p-6 text-green-800"
          >
            Thank you for your message. We&apos;ll get back to you within one business day.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-8 space-y-5 rounded-2xl border border-surface-border bg-white p-8 shadow-sm">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-slate-700">
                Name
              </label>
              <input
                id="name"
                name="name"
                type="text"
                required
                autoComplete="name"
                className="mt-1 w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                className="mt-1 w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
              />
            </div>
            <div>
              <label htmlFor="company" className="block text-sm font-medium text-slate-700">
                Company
              </label>
              <input
                id="company"
                name="company"
                type="text"
                autoComplete="organization"
                className="mt-1 w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
              />
            </div>
            <div>
              <label htmlFor="message" className="block text-sm font-medium text-slate-700">
                Message
              </label>
              <textarea
                id="message"
                name="message"
                rows={5}
                required
                className="mt-1 w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
              />
            </div>
            <Button type="submit" className="w-full">
              Send Message
            </Button>
          </form>
        )}
      </div>
    </section>
  );
}
