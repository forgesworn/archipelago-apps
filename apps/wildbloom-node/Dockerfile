# syntax=docker/dockerfile:1
# Builds wildbloomd from a pinned commit. Runs as container root, which under
# Archipelago's rootless Podman is the unprivileged archipelago user on the host,
# so the /data bind mount is writable without uid juggling.
FROM rust:1.94.1-slim-trixie AS build
ARG WILDBLOOM_NODE_REF
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init -q && git remote add origin https://github.com/forgesworn/wildbloom-node.git \
    && git fetch -q --depth 1 origin "${WILDBLOOM_NODE_REF}" && git checkout -q FETCH_HEAD
RUN cargo build --release --locked -p wildbloomd

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/wildbloomd /usr/local/bin/wildbloomd
ENV WILDBLOOM_DATA_DIR=/data \
    WILDBLOOM_NO_TOR=true \
    WILDBLOOM_BIND=0.0.0.0:3742 \
    WILDBLOOM_ALLOW_PUBLIC_BIND=true
EXPOSE 3742
ENTRYPOINT ["/usr/local/bin/wildbloomd"]
