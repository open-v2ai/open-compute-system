import type { NextConfig } from "next";

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
if (basePath && !/^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(basePath)) {
  throw new Error("NEXT_PUBLIC_BASE_PATH must be an absolute path without a trailing slash");
}

const nextConfig: NextConfig = {
  output: "standalone",
  basePath,
  devIndicators: false,
  experimental: { cpus: 2 },
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
  async redirects() {
    return [
      { source: "/market/group-buying", destination: "/market", permanent: false },
      { source: "/market/bare-metal", destination: "/market", permanent: false },
      { source: "/solutions", destination: "/", permanent: false },
      { source: "/admin/leads", destination: "/admin", permanent: false },
    ];
  },
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` },
      { source: "/health/:path*", destination: `${apiOrigin}/health/:path*` },
    ];
  },
};

export default nextConfig;
