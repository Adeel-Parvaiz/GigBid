FROM node:22-slim AS build
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /web/dist /usr/share/nginx/html
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
