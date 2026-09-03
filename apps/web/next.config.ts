import type { NextConfig } from "next";
const apiOrigin = process.env.MOVON_API_ORIGIN || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};
export default nextConfig;
