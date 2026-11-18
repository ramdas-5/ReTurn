import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import Providers from "./providers";
import { palette } from "@/lib/design-tokens";
import "./globals.css";

/**
 * DESIGN.md §Style Foundations — Saans is the primary family. It is a licensed
 * face and is not redistributed with this repository, so the CSS stack puts
 * "Saans" first and ships Inter (same grotesque proportions, 16/24 metrics) as
 * the metric-compatible fallback.
 */
const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "ReTurn — Smart Reverse Delivery & Shared Logistics",
    template: "%s · ReTurn",
  },
  description:
    "ReTurn coordinates compatible product returns and parcel deliveries into feasible shared routes. One route. Multiple deliveries. Less waste.",
  applicationName: "ReTurn",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: palette.accent,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
