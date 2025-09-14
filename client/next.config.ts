import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    domains: [
      'oaidalleapiprodscus.blob.core.windows.net',
      'replicate.delivery'
    ],
  },
  reactStrictMode: false,  // Disable double rendering in development
};

export default nextConfig;
