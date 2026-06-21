/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The API URL is read by lib/api/client.ts at runtime. Listed here for
  // visibility — Next surfaces NEXT_PUBLIC_* in the browser bundle.
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
};

export default nextConfig;
