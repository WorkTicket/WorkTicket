import Link from "next/link";

const footerLinks = {
  Product: [
    { href: "/features", label: "Features" },
    { href: "/pricing", label: "Pricing" },
    { href: "/blog", label: "Blog" },
  ],
  Company: [
    { href: "/about", label: "About" },
    { href: "/contact", label: "Contact" },
  ],
  Legal: [
    { href: "/privacy", label: "Privacy Policy" },
    { href: "/terms", label: "Terms of Service" },
  ],
};

export function SiteFooter() {
  return (
    <footer className="border-t border-surface-border bg-surface-muted" role="contentinfo">
      <div className="container-content section-padding">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-lg font-bold text-brand-700">WorkTicket</p>
            <p className="mt-3 text-sm text-slate-600">
              Job management software built for skilled trades businesses.
            </p>
          </div>
          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
              <ul className="mt-4 space-y-2">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-slate-600 hover:text-slate-900">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 border-t border-surface-border pt-8 text-sm text-slate-500">
          &copy; {new Date().getFullYear()} WorkTicket. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
