/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Get backend API URL from environment variable, fallback to localhost for development
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    // Only use rewrites in development (when API_URL points to localhost)
    // In production, we'll use the actual backend URL directly
    if (process.env.NODE_ENV === 'development' || apiUrl.includes('localhost')) {
      return [
        {
          source: '/api/chat/:path*',
          destination: `${apiUrl}/api/chat/:path*`,
        },
        {
          source: '/api/webhooks/:path*',
          destination: `${apiUrl}/api/webhooks/:path*`,
        },
        {
          source: '/api/user/:path*',
          destination: `${apiUrl}/api/user/:path*`,
        },
      ];
    }
    
    // In production, return empty array (no rewrites needed)
    return [];
  },
};

export default nextConfig;
