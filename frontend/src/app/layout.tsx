import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { AppProviders } from "@/providers/query-provider";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const viewport: Viewport = {
  themeColor: "#190D08",
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "DRIP & RHYTHM — Private Party | 5 December 2026",
    template: "%s | DRIP & RHYTHM",
  },
  description:
    "An affair of fashion, music and culture. Presented by After Dark Events × Hype District on 5 December 2026 in Muyenga, Kampala.",
  manifest: "/site.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "DRIP & RHYTHM — Private Party",
    description:
      "An affair of fashion, music and culture · 5 December 2026 · Muyenga, Kampala · Invitation Only (18+).",
    url: siteUrl,
    siteName: "DRIP & RHYTHM",
    images: [
      {
        url: "/branding/event-poster.jpeg",
        width: 1024,
        height: 1024,
        alt: "DRIP & RHYTHM Private Party — 5 December 2026",
      },
    ],
    type: "website",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-midnight text-ivory antialiased selection:bg-burnt selection:text-ivory">
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
