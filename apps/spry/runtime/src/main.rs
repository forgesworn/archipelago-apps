#![forbid(unsafe_code)]

fn main() {
    spry_service::main_with_assets(spry_service::UiAssets {
        index: include_str!("../../public/index.html"),
        script: spry_service::UiAssets::STANDALONE.script,
        style: spry_service::UiAssets::STANDALONE.style,
        signer_provider: Some(include_str!("../../public/nostr-provider.js")),
    });
}
