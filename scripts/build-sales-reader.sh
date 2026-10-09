#!/usr/bin/env bash
# Compile the dashboard's actual read-only projection for packaged-node acceptance.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archy=$(cd "${1:?Pass patched Archy checkout}" && pwd)
fixture="$root/.cache/sales-reader"
mkdir -p "$fixture/src"
cp "$archy/core/archipelago/src/settings/wildbloom_sales.rs" "$fixture/src/sales.rs"
cat > "$fixture/Cargo.toml" <<'TOML'
[package]
name = "sales-reader"
version = "0.0.0"
edition = "2021"
[workspace]
[dependencies]
anyhow = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
rusqlite = { version = "=0.40.2", features = ["bundled"] }
TOML
# Keep the source module's numeric boundary, without importing unrelated settings.
rg '^pub const MAX:' "$archy/core/archipelago/src/settings/wildbloom_storage.rs" > "$fixture/src/wildbloom_storage.rs"
cat > "$fixture/src/main.rs" <<'RS'
mod wildbloom_storage;
mod sales;
fn main() -> anyhow::Result<()> {
    let root = std::env::args().nth(1).expect("synthetic node directory");
    println!("{}", sales::read(std::path::Path::new(&root), true, &sales::PageRequest::default())?);
    Ok(())
}
RS
cargo build --quiet --manifest-path "$fixture/Cargo.toml"
