import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  poweredByHeader: false,
  allowedDevOrigins: ["frontend", "frontend-auth-test"],
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
};
export default nextConfig;
