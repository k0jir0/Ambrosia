FROM node:20.18.1-bookworm-slim AS builder
ENV NEXT_TELEMETRY_DISABLED=1
RUN apt-get update \
    && apt-get dist-upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable \
    && corepack prepare pnpm@9.12.0 --activate
WORKDIR /workspace
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json apps/web/package.json
COPY apps/mobile/package.json apps/mobile/package.json
RUN pnpm install --frozen-lockfile --filter @ambrosia/web...
COPY apps/web apps/web
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_ENABLE_LABS=false
ARG NEXT_PUBLIC_ENABLE_MARKET_SCANNER=false
ARG NEXT_PUBLIC_ENABLE_MARKET_SCANNER_PROMOTION=false
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_ENABLE_LABS=${NEXT_PUBLIC_ENABLE_LABS}
ENV NEXT_PUBLIC_ENABLE_MARKET_SCANNER=${NEXT_PUBLIC_ENABLE_MARKET_SCANNER}
ENV NEXT_PUBLIC_ENABLE_MARKET_SCANNER_PROMOTION=${NEXT_PUBLIC_ENABLE_MARKET_SCANNER_PROMOTION}
ENV NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL}
RUN pnpm --filter @ambrosia/web build

FROM node:20.18.1-bookworm-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN apt-get update \
    && apt-get dist-upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/node_modules/npm \
        /usr/local/lib/node_modules/corepack \
        /opt/yarn-v1.22.22 \
    && rm -f /usr/local/bin/npm \
        /usr/local/bin/npx \
        /usr/local/bin/corepack \
        /usr/local/bin/yarn \
        /usr/local/bin/yarnpkg \
        /usr/local/bin/pnpm \
        /usr/local/bin/pnpx \
    && useradd --create-home --uid 10001 ambrosia
WORKDIR /app
COPY --from=builder --chown=ambrosia:ambrosia /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=ambrosia:ambrosia /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=ambrosia:ambrosia /workspace/apps/web/public ./apps/web/public
USER ambrosia
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "apps/web/server.js"]
