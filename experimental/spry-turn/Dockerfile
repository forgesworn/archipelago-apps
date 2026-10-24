# syntax=docker/dockerfile:1
# A private, local build context is prepared from an exact reviewed commit.
# No repository credentials or operator secrets belong in this context.
FROM rust:1.94.1-slim-trixie AS build
WORKDIR /src
COPY source/ ./
RUN cargo build --locked --release --features tls --bin spry-turn

FROM debian:trixie-slim
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.description="Experimental operator-owned Spry TURN transport"
COPY --from=build /src/target/release/spry-turn /usr/local/bin/spry-turn
COPY source/LICENSE source/NOTICE source/THIRD_PARTY_LICENSES.txt /usr/share/doc/spry-turn/
ENTRYPOINT ["/usr/local/bin/spry-turn"]
