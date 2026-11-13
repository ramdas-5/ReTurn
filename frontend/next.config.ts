import type { NextConfig } from "next";

/**
 * The browser always calls same-origin `/api/v1/*`. This rewrite forwards those
 * requests to the Flask REST API so the HttpOnly session cookie and CSRF cookie
 * remain first-party (no CORS, no cross-site cookie problems).
 *
 * `FLASK_API_URL` is server-only and must never be exposed as NEXT_PUBLIC_*.
 */
const flaskApiUrl = (process.env.FLASK_API_URL ?? "http://127.0.0.1:5000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  // Vercel manages its own output; `standalone` is only for self-hosted/Docker.
  output: process.env.VERCEL ? undefined : "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${flaskApiUrl}/api/v1/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
