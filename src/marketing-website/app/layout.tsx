import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://workticket.app"),
  title: {
    default: "WorkTicket — Job Management for Skilled Trades",
    template: "%s | WorkTicket",
  },
  description:
    "WorkTicket helps HVAC, plumbing, electrical, and other skilled trades businesses manage jobs, estimates, scheduling, and field teams — manual-first, built for contractors.",
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "WorkTicket",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen font-sans">
        <SiteHeader />
        <main id="main-content">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
