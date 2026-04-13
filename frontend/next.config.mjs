import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  /**
   * Prevent Turbopack from inferring the monorepo root (which causes huge watch
   * sets and can hit Linux inotify limits). Keep it scoped to this app only.
   */
  experimental: {
    turbo: {
      root: path.resolve(__dirname),
    },
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
      { protocol: "https", hostname: "fastly.picsum.photos" },
      { protocol: "https", hostname: "images.unsplash.com" },
      // Django media (dev)
      { protocol: "http", hostname: "127.0.0.1", port: "8000", pathname: "/media/**" },
      { protocol: "http", hostname: "localhost", port: "8000", pathname: "/media/**" },
      // Allow other upstreams (prod CDNs)
      { protocol: "https", hostname: "**" },
      { protocol: "http", hostname: "**" },
    ],
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  async rewrites() {
    const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return {
      beforeFiles: [
        // /api/v1 is handled by src/app/api/v1/[...path]/route.ts (no external rewrite needed).
        { source: "/media/:path*", destination: `${apiUrl}/media/:path*` },
      ],
      afterFiles: [],
    };
  },
};

export default nextConfig;
