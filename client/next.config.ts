import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output is only wanted for the Docker image; `next start` refuses to
  // serve it, so it stays off for local runs.
  output: process.env.BUILD_STANDALONE === "true" ? "standalone" : undefined,
  // The evidence-download proxy streams files from object storage; keep responses
  // uncompressed so large PDFs are not buffered twice.
  compress: true,
  eslint: {
    dirs: ["app", "components", "lib", "hooks", "stores", "types"],
  },
};

export default nextConfig;
