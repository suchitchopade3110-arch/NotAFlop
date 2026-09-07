import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  eslint: {
    // CI runs lint as its own step (D4) — don't double-run it inside build.
    ignoreDuringBuilds: true,
  },
  // D4/D5: standalone output for a minimal production Docker image
  // (frontend/Dockerfile copies only .next/standalone + static + public).
  output: "standalone",
};

export default nextConfig;
