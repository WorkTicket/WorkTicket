"use client";

import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { signUpUrl } from "@/lib/utils";

const highlights = [
  "Jobs, estimates, and scheduling in one place",
  "Built for HVAC, plumbing, electrical, and more",
  "Mobile app for field technicians",
];

export function Hero() {
  return (
    <section className="section-padding bg-gradient-to-b from-brand-50/50 to-white">
      <div className="container-content">
        <div className="mx-auto max-w-3xl text-center">
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-sm font-semibold uppercase tracking-wide text-brand-600"
          >
            Job management for skilled trades
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05 }}
            className="mt-4 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl"
          >
            Run your jobs without the paperwork chaos
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mt-6 text-lg text-slate-600 sm:text-xl"
          >
            WorkTicket helps contractors manage customers, jobs, estimates, photos, and team
            scheduling — so your crew spends more time on site and less time in the office.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row"
          >
            <ButtonLink href={signUpUrl()} size="lg" className="gap-2">
              Start Free Trial
              <ArrowRight className="h-4 w-4" aria-hidden />
            </ButtonLink>
            <ButtonLink href="/features" variant="secondary" size="lg">
              See Features
            </ButtonLink>
          </motion.div>
          <motion.ul
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.25 }}
            className="mt-10 flex flex-col items-start gap-3 text-left sm:items-center"
            aria-label="Product highlights"
          >
            {highlights.map((item) => (
              <li key={item} className="flex items-center gap-2 text-sm text-slate-600">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-brand-600" aria-hidden />
                {item}
              </li>
            ))}
          </motion.ul>
        </div>
      </div>
    </section>
  );
}
