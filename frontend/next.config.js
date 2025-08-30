/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
  images: {
    domains: ['localhost'],
  },
  env: {
    NEXT_PUBLIC_GRAPHQL_URL: process.env.NEXT_PUBLIC_GRAPHQL_URL || 'http://localhost:4000/graphql',
    NEXT_PUBLIC_RAG_SERVICE_URL: process.env.NEXT_PUBLIC_RAG_SERVICE_URL || 'http://localhost:8000',
  },
}

module.exports = nextConfig
