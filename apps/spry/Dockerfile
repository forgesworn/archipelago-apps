# syntax=docker/dockerfile:1
FROM rust:1.94.1-slim-trixie AS relay
ARG SPRY_REF=367efc77c84db7a20eddf70ab243dcd13d9065ef
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git init /src && cd /src && git remote add origin https://github.com/forgesworn/spry-turn.git && git fetch --depth 1 origin "$SPRY_REF" && git checkout --detach FETCH_HEAD && test "$(git rev-parse HEAD)" = "$SPRY_REF"
WORKDIR /src
RUN cargo build --locked --release --features tls --bin spry-turn

FROM rust:1.94.1-slim-trixie AS control
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY apps/spry/runtime/ ./apps/spry/runtime/
COPY apps/spry/public/ ./apps/spry/public/
RUN cargo build --locked --release -p spry-node

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates iproute2 && rm -rf /var/lib/apt/lists/*
COPY --from=relay /src/target/release/spry-turn /usr/local/bin/spry-turn
COPY --from=control /src/target/release/spry-node /usr/local/bin/spry-node
COPY --from=relay /src/LICENSE /src/NOTICE /src/THIRD_PARTY_LICENSES.txt /usr/share/doc/spry-turn/
COPY LICENSE /usr/share/doc/spry-node/LICENSE
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.source=https://github.com/forgesworn/archipelago-apps
ENTRYPOINT ["/usr/local/bin/spry-node"]
