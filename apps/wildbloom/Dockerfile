# syntax=docker/dockerfile:1
FROM node:24.19.0-trixie-slim AS build
ARG WILDBLOOM_REF
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init -q && git remote add origin https://github.com/forgesworn/wildbloom.git \
    && git fetch -q --depth 1 origin "${WILDBLOOM_REF}" && git checkout -q FETCH_HEAD
RUN npm ci && npm run build

FROM nginx:1.29-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/wildbloom.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 3743
