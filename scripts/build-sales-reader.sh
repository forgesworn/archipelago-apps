#!/usr/bin/env bash
# Compile the dashboard's actual read-only projection for packaged-node acceptance.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archy=$(cd "${1:?Pass patched Archy checkout}" && pwd)
fixture="$root/.cache/sales-reader"
mkdir -p "$fixture/src"
for module in wildbloom_sales wildbloom_storage wildbloom_refunds; do
  cp "$archy/core/archipelago/src/settings/$module.rs" "$fixture/src/$module.rs"
done
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
uuid = { version = "1", features = ["v4"] }
tokio = { version = "1", features = ["sync"] }
reqwest = { version = "0.12", default-features = false }
[dev-dependencies]
tempfile = "3"
TOML
cat > "$fixture/src/main.rs" <<'RS'
#[allow(dead_code)]
mod wildbloom_storage;
mod wildbloom_sales;
mod wildbloom_refunds;
fn main() -> anyhow::Result<()> {
    let args: Vec<_> = std::env::args().collect();
    let root = args.get(1).expect("synthetic node directory");
    if args.get(2).is_some_and(|v| v == "--record-refund") {
        let request = wildbloom_refunds::Request { order_id: args[3].clone(), amount_msat: args[4].parse()?,
            payment_hash: args[5].clone(), confirm_received: true };
        wildbloom_refunds::record(std::path::Path::new(&root), request)?;
    }
    println!("{}", wildbloom_sales::read(std::path::Path::new(&root), true, &wildbloom_sales::PageRequest::default())?);
    Ok(())
}
RS
cargo build --quiet --manifest-path "$fixture/Cargo.toml"
