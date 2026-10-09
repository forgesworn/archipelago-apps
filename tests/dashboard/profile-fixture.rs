// Linked to the actual dashboard configuration module by the fixture runner.
use std::net::IpAddr;
fn main() {
    let mut settings = storage::Settings::defaults(100);
    settings.owner_reserved_bytes = 40;
    settings.offer_capacity_bytes = 60;
    settings.max_blob_bytes = 100;
    settings.price_sats = 1;
    settings.sales_enabled = true;
    settings.moneyer_terms_accepted = true;
    settings.moneyer_ips = vec!["1.1.1.1".parse::<IpAddr>().unwrap()];
    settings.refund_policy = "Synthetic local acceptance only; no real payment.".into();
    settings.validate().unwrap();
    settings.validate_receiver().unwrap();
    let active = storage::Active { revision: 2, origin: "https://storage.example:3742".into(), checkout_started: true, settings };
    println!("{}", storage::profile(&active));
}
