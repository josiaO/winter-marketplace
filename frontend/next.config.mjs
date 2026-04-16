import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
      { protocol: "https", hostname: "fastly.picsum.photos" },
      { protocol: "https", hostname: "images.unsplash.com" },
      // Django media (dev)
      { protocol: "http", hostname: "127.0.0.1", port: "8000", pathname: "/media/**" },
      { protocol: "http", hostname: "localhost", port: "8000", pathname: "/media/**" },
      // Production Storage (Cloudfront / S3 / Cloudinary etc.)
      // { protocol: "https", hostname: "cdn.smartdalali.com" },
    ],
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  reactStrictMode: false,
  optimizeFonts: false,
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
