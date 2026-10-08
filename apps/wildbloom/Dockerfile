# syntax=docker/dockerfile:1
FROM node:24.19.0-trixie-slim AS build
ARG WILDBLOOM_REF
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init -q && git remote add origin https://github.com/forgesworn/wildbloom.git \
    && git fetch -q --depth 1 origin "${WILDBLOOM_REF}" && git checkout -q FETCH_HEAD
RUN npm ci --ignore-scripts && npm run build && npm run audit

FROM nginx:1.29-alpine
LABEL org.opencontainers.image.source=https://github.com/forgesworn/archipelago-apps
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.description="Wildbloom web app for Archipelago: encrypted files, replicated and coded storage pools, recovery and audits, signed by your node identities."
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/wildbloom.conf
COPY --chmod=755 15-wildbloom-ipv6.sh /docker-entrypoint.d/15-wildbloom-ipv6.sh
COPY --from=build /src/dist /usr/share/nginx/html
COPY archipelago-node.js /usr/share/nginx/html/archipelago-node.js
COPY --chmod=755 20-archipelago-node.sh /docker-entrypoint.d/20-archipelago-node.sh
# Archipelago's NIP-07 provider, vendored byte-identical from archy at ARCHY_REF
# (neode-ui/public/nostr-provider.js, MIT, (c) Dorian and the Archipelago Project
# contributors). Baked in, as IndeeHub does, so it survives the node recreating
# the container; the manifest's copy_from_host hook refreshes it at install.
# scripts/validate.sh fails if it drifts from the pinned copy. Copied after dist
# so nothing overwrites it.
COPY nostr-provider.js /usr/share/nginx/html/nostr-provider.js
EXPOSE 3743
