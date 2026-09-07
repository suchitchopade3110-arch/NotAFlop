import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AnalyticsProvider } from "@/lib/analytics/provider";
import { SessionBootstrap } from "@/lib/store/session-bootstrap";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["500", "600"],
  display: "swap",
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "NotAFlop: validate your startup idea before you build it",
    template: "%s · NotAFlop",
  },
  description:
    "Pitch your idea. Get a scored verdict grounded in live market signals. Free forever, no account required.",
  openGraph: {
    title: "NotAFlop",
    description: "Validate your startup idea before you build it. Free forever.",
    url: siteUrl,
    siteName: "NotAFlop",
  },
  twitter: {
    card: "summary_large_image",
    title: "NotAFlop",
    description: "Validate your startup idea before you build it. Free forever.",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0a0b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} antialiased`}
      >
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-charcoal-raised focus:px-4 focus:py-2 focus:text-mono focus:text-gold-bright"
        >
          Skip to content
        </a>
        <AnalyticsProvider>
          <SessionBootstrap />
          {children}
        </AnalyticsProvider>
      </body>
    </html>
  );
}
