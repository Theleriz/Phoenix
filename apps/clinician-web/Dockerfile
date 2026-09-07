FROM node:22-alpine AS build
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/clinician-web/package.json apps/clinician-web/package.json
COPY packages/ui/package.json packages/ui/package.json
RUN npm ci --no-audit --no-fund
COPY apps/clinician-web apps/clinician-web
COPY packages/ui packages/ui
RUN npm run build --workspace=apps/clinician-web

FROM nginx:1.27-alpine

COPY apps/clinician-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/clinician-web/dist /usr/share/nginx/html
