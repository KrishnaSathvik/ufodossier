/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: false,
  },
  // Catalog JSON lives outside web/. Include it in every serverless trace so
  // dynamic routes like /audio and /releases can read it at runtime on Vercel.
  outputFileTracingIncludes: {
    "/*": [
      "../pipeline/reports/corpus_qa/**/*",
      "../pipeline/snapshots/pursue/2026-09-18-official/records.json",
      "../pipeline/reports/r2_smoke/extractions.json",
      "../pipeline/reports/r2_complete/odni_extraction.json",
      "../pipeline/reports/r3_full/extractions.json",
      "../pipeline/reports/r3_truncation_fix/results.json",
      "../pipeline/reports/r4_local/extractions.json",
      "../pipeline/reports/r5_local/extractions.json",
      "../pipeline/reports/r6_local/extractions.json",
    ],
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.supabase.co" },
      { protocol: "https", hostname: "www.war.gov" },
      { protocol: "https", hostname: "**.cloudfront.net" },
    ],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};
module.exports = nextConfig;
