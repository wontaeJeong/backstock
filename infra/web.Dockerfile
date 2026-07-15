FROM node:24-alpine

RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web

CMD ["pnpm", "--filter", "@backstock/web", "dev", "--hostname", "0.0.0.0"]
