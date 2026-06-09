import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "@/components/providers";
import { SkipLink } from "@/components/skip-link";
import { ErrorBoundary } from "@/components/error-boundary";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: {
    default: "WorkTicket Dashboard",
    template: "%s | WorkTicket",
  },
  description: "Job management software for skilled trades",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <ClerkProvider nonce={nonce}>
      <html lang="en" suppressHydrationWarning>
        <body>
          <SkipLink />
          <Providers>
            <ErrorBoundary>{children}</ErrorBoundary>
          </Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
