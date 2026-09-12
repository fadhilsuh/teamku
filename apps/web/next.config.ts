import type { NextConfig } from "next";

// Browser selalu bicara same-origin ke /api; Next mem-proxy ke FastAPI.
// Itu yang menjaga cookie sesi tetap first-party (host-only, SameSite=Lax)
// sehingga tidak perlu CORS maupun perubahan pada jalur auth.
//
// Nilai ini dibakukan ke routes-manifest.json saat build, bukan dibaca saat
// runtime — lihat scripts/require-api-origin.mjs.
const target = process.env.MOVON_API_ORIGIN || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Dibutuhkan Dockerfile untuk compose lokal. Vercel memakai pipeline build
  // sendiri, jadi dimatikan di sana agar tidak ada artefak yang mubazir.
  output: process.env.VERCEL ? undefined : "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${target}/api/v1/:path*` }];
  },
};

export default nextConfig;
