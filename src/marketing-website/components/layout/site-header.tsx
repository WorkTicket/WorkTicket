"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { cn, signInUrl, signUpUrl } from "@/lib/utils";

const navLinks = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
  { href: "/blog", label: "Blog" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-surface-border bg-white/90 backdrop-blur-md">
      <div className="container-content flex h-16 items-center justify-between">
        <Link href="/" className="text-lg font-bold text-brand-700" aria-label="WorkTicket home">
          WorkTicket
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Main navigation">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <ButtonLink href={signInUrl()} variant="ghost" size="sm">
            Sign In
          </ButtonLink>
          <ButtonLink href={signUpUrl()} size="sm">
            Start Free Trial
          </ButtonLink>
        </div>

        <button
          type="button"
          className="rounded-md p-2 text-slate-600 hover:bg-slate-100 md:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen(!open)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      <nav
        id="mobile-nav"
        className={cn("border-t border-surface-border bg-white md:hidden", open ? "block" : "hidden")}
        aria-label="Mobile navigation"
      >
        <div className="container-content flex flex-col gap-1 py-4">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          <div className="mt-3 flex flex-col gap-2 border-t border-surface-border pt-4">
            <ButtonLink href={signInUrl()} variant="secondary" className="w-full">
              Sign In
            </ButtonLink>
            <ButtonLink href={signUpUrl()} className="w-full">
              Start Free Trial
            </ButtonLink>
          </div>
        </div>
      </nav>
    </header>
  );
}
