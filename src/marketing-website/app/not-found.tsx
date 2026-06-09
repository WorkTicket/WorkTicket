import Link from "next/link";
import { ButtonLink } from "@/components/ui/button";

export default function NotFound() {
  return (
    <section className="section-padding text-center">
      <div className="container-content mx-auto max-w-lg">
        <p className="text-sm font-semibold text-brand-600">404</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Page not found</h1>
        <p className="mt-4 text-slate-600">The page you&apos;re looking for doesn&apos;t exist or has moved.</p>
        <div className="mt-8 flex justify-center gap-3">
          <ButtonLink href="/">Go Home</ButtonLink>
          <Link href="/contact" className="text-sm font-medium text-brand-600 hover:underline self-center">
            Contact Support
          </Link>
        </div>
      </div>
    </section>
  );
}
