import type { Metadata, Viewport } from "next";
import { Poppins } from "next/font/google";

import Providers from "./providers";
import { palette } from "@/lib/design-tokens";
import "./globals.css";

/** DESIGN.md §Style Foundations — Poppins is the primary family. */
const primary = Poppins({
  subsets: ["latin"],
  variable: "--font-poppins",
  display: "swap",
  weight: ["400", "500", "600", "700"],
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
  themeColor: palette.base,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={primary.variable}>
      <body className="on-dark">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
