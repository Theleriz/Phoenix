FROM node:22-alpine AS build
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/patient-web/package.json apps/patient-web/package.json
COPY packages/ui/package.json packages/ui/package.json
RUN npm ci --no-audit --no-fund
COPY apps/patient-web apps/patient-web
COPY packages/ui packages/ui
# Vite inlines VITE_* variables at build time, not runtime -- this must be an
# ARG passed through from `docker compose build.args`, not a container ENV.
ARG VITE_PHOENIX_GATEWAY_TOKEN
ENV VITE_PHOENIX_GATEWAY_TOKEN=$VITE_PHOENIX_GATEWAY_TOKEN
RUN npm run build --workspace=apps/patient-web

FROM nginx:1.27-alpine

COPY apps/patient-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/patient-web/dist /usr/share/nginx/html
