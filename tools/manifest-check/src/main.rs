//! Parse and validate Archipelago manifests with Archipelago's own parser,
//! which is the canonical schema (`core/container/src/manifest.rs`).
use archipelago_container::manifest::AppManifest;
use std::process::ExitCode;

fn main() -> ExitCode {
    let mut failed = false;
    for path in std::env::args().skip(1) {
        let outcome = std::fs::read_to_string(&path)
            .map_err(|e| e.to_string())
            .and_then(|text| AppManifest::parse(&text).map(|_| ()).map_err(|e| e.to_string()));
        match outcome {
            Ok(()) => println!("OK {path}"),
            Err(e) => {
                println!("FAIL {path}: {e}");
                failed = true;
            }
        }
    }
    if failed { ExitCode::FAILURE } else { ExitCode::SUCCESS }
}
