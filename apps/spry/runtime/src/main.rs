#![forbid(unsafe_code)]

fn main() {
    spry_service::main_with_assets(spry_service::UiAssets {
        index: include_str!("../../public/index.html"),
        script: include_str!("../../public/app.mjs"),
        style: include_str!("../../public/style.css"),
        signer_provider: Some(include_str!("../../public/nostr-provider.js")),
    });
}
