/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['dd.dexscreener.com', 'raw.githubusercontent.com'],
  },
  async rewrites() {
    // Use API_URL for server-side rewrite (not NEXT_PUBLIC_ which is client-only)
    const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
