import path from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const isDevelopment = process.env.NODE_ENV !== "production";
const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const configuredApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL;
const localApiUpstream = process.env.AMBROSIA_LOCAL_API_UPSTREAM ?? "http://127.0.0.1:8000";
let apiConnectSource = "";
try {
  apiConnectSource = configuredApiUrl && !configuredApiUrl.startsWith("/")
    ? ` ${new URL(configuredApiUrl).origin}`
    : "";
} catch {
  throw new Error("NEXT_PUBLIC_API_BASE_URL must be an absolute URL or a same-origin path beginning with /");
}

const nextConfig = {
  // Windows workspaces commonly deny the symlinks used by standalone tracing.
  // AWS/container builds run on Linux and still emit the deployable server.
  output: process.platform === "win32" ? undefined : "standalone",
  outputFileTracingRoot: path.join(projectDirectory, "../.."),
  reactStrictMode: true,
  poweredByHeader: false,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    if (!isDevelopment || configuredApiUrl !== "/api") return [];
    return [
      {
        source: "/api/:path*",
        destination: `${localApiUpstream}/:path*`
      }
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "base-uri 'self'",
              "frame-ancestors 'none'",
              "form-action 'self'",
              "img-src 'self' data: blob:",
              "font-src 'self' data:",
              "style-src 'self' 'unsafe-inline'",
              `script-src 'self' 'unsafe-inline'${isDevelopment ? " 'unsafe-eval'" : ""}`,
              `connect-src 'self'${apiConnectSource}${isDevelopment ? " http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*" : ""}`,
              "object-src 'none'",
              ...(isDevelopment ? [] : ["upgrade-insecure-requests"])
            ].join("; ")
          }
        ]
      }
    ];
  }
};

export default nextConfig;
