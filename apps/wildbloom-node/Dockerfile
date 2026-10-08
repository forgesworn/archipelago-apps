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
COPY checkout-sales-capacity.patch shelter-sales-capacity.patch /patches/
# Package-scoped patches against the exact Node and Shelter inputs. Keep the
# original repositories untouched; replace these with upstream pins when merged.
RUN git clone --quiet --no-checkout https://github.com/forgesworn/shelter-kit.git vendor/shelter-kit \
    && git -C vendor/shelter-kit checkout --quiet c573ca3da5725fb8bf3d2593ae2c07b0278289a5 \
    && git -C vendor/shelter-kit apply --check /patches/shelter-sales-capacity.patch \
    && git -C vendor/shelter-kit apply /patches/shelter-sales-capacity.patch \
    && git apply --check /patches/checkout-sales-capacity.patch \
    && git apply /patches/checkout-sales-capacity.patch
RUN cargo test --locked -p wildbloom-checkout \
    && cargo test --locked --manifest-path vendor/shelter-kit/Cargo.toml --lib \
    && cargo build --release --locked -p wildbloomd -p wildbloom-checkout --bin wildbloomd --bin checkout-operator

FROM debian:trixie-slim
LABEL org.opencontainers.image.source=https://github.com/forgesworn/archipelago-apps
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.description="Wildbloom Node: Blossom storage on your Archipelago node, owned by your node's Nostr identity."
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/wildbloomd /usr/local/bin/wildbloomd
COPY --from=build /src/target/release/checkout-operator /usr/local/bin/checkout-operator
ENV WILDBLOOM_DATA_DIR=/data \
    WILDBLOOM_NO_TOR=true \
    WILDBLOOM_BIND=0.0.0.0:3742 \
    WILDBLOOM_ALLOW_PUBLIC_BIND=true
EXPOSE 3742
ENTRYPOINT ["/usr/local/bin/wildbloomd"]
