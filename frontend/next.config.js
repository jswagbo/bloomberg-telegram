/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['dd.dexscreener.com', 'raw.githubusercontent.com'],
  },
  // API requests are now handled by the /api/v1/[[...path]]/route.ts API route
  // which reads API_URL at runtime (not build time), ensuring proper proxy behavior
};

module.exports = nextConfig;
