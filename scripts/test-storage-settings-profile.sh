#!/usr/bin/env bash
# Build a fixture from the real Rust profile generator, then load it into the
# actual Node image. No issuer calls or payments; disposable storage only.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archy=${1:-$root/.cache/archy-selling}
image=${2:?Pass the packaged Wildbloom Node image}
archy=$(cd "$archy" && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
mkdir "$fixture/src"
cat > "$fixture/Cargo.toml" <<'TOML'
[package]
name = "storage-settings-fixture"
version = "0.0.0"
edition = "2021"
[workspace]
[dependencies]
anyhow = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["sync"] }
uuid = { version = "1", features = ["v4"] }
TOML
cp "$archy/core/archipelago/src/settings/wildbloom_storage.rs" "$fixture/src/storage.rs"
printf 'mod storage;\n' > "$fixture/src/main.rs"
cat "$root/tests/dashboard/profile-fixture.rs" >> "$fixture/src/main.rs"
cargo run --quiet --manifest-path "$fixture/Cargo.toml" > "$fixture/profile.json"
cd "$root"
node tests/smoke/seller-capacity.mjs "$image" "$fixture/profile.json"
