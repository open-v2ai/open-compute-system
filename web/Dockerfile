FROM node:25-alpine AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.20.0 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts

FROM node:25-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NODE_BUILD_MEMORY_MB=1536
ENV NODE_OPTIONS=--max-old-space-size=${NODE_BUILD_MEMORY_MB}
ARG API_ORIGIN=http://api:8000
ENV API_ORIGIN=$API_ORIGIN
ARG NEXT_PUBLIC_CSRF_COOKIE=ocs_csrf
ENV NEXT_PUBLIC_CSRF_COOKIE=$NEXT_PUBLIC_CSRF_COOKIE
ARG NEXT_PUBLIC_BASE_PATH=
ARG NEXT_PUBLIC_PUBLIC_DEMO=false
ARG NEXT_PUBLIC_DEMO_ORIGIN=
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH \
    NEXT_PUBLIC_PUBLIC_DEMO=$NEXT_PUBLIC_PUBLIC_DEMO \
    NEXT_PUBLIC_DEMO_ORIGIN=$NEXT_PUBLIC_DEMO_ORIGIN
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable && corepack prepare pnpm@11.20.0 --activate && pnpm build

FROM node:25-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

