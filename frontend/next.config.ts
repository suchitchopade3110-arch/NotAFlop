import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  eslint: {
    // CI runs lint as its own step (D4) — don't double-run it inside build.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
