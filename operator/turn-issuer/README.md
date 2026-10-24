# Public demo TURN credentials

This optional operator service supplies expiring Spry passwords to the public
ForgeSworn media demo. It does not add a service to KithMoot. The independently
operated node handles the relay and its credentials.

The HTTP runtime is a dependency-free Rust binary, separate from the media
forwarding path. A root-only timer invokes the installed Spry CLI to mint a
64-entry pool every five minutes. Each password expires after 20 minutes. The
unprivileged HTTP process can read the pool and its consumption cursor; it has
no access to the root TURN secret, container socket or private dashboard.
The cursor survives a service restart. Atomic pool replacement does not
invalidate credentials that browsers already hold.

The reviewed configuration uses a separate trusted HTTPS listener on TCP7443.
Only `/turn-credentials` is forwarded. Every other path returns 404. The
dashboard's firewall rules and the relay binary are preserved. The certificate
is the existing operator-managed certificate; its renewal already reloads nginx.

The browser sends `POST` with `{"v":1}` and `Origin: https://forgesworn.dev`.
An allowed preflight returns 204. Missing or different origins are rejected.
Responses use `Cache-Control: no-store`; browser requests omit cookies. CORS
controls browser access; this is intentionally an anonymous public demo
issuer, not account authentication. Non-browser clients can reproduce an
Origin header, so issuance and TURN allocations remain resource bounded.

The runtime permits at most four active HTTP handlers, 2KiB request headers,
128-byte bodies, 32 issued credentials per minute and 12 per source IP per
minute. The pool contains at most 64 issued credentials per refill. nginx
adds connection and request limits. The service has 24MiB memory, 10% CPU,
eight tasks and 32 file-descriptor limits. No request or password logs are
written. Spry's separate allocation, per-user and bandwidth limits still apply.

The browser refreshes its lease at two thirds of the returned remaining
lifetime and coalesces in-flight requests. New connections use the latest
credentials. Established relayed channels are retired before their original
lease expires so RelaySwarm can reconnect without replacing the video or its
verified cache. Direct connections stay open. An unavailable issuer leaves
ordinary HTTPS video playback available and retries in the background.

## Verify and build

```sh
cargo fmt --manifest-path operator/turn-issuer/Cargo.toml -- --check
cargo clippy --locked --manifest-path operator/turn-issuer/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path operator/turn-issuer/Cargo.toml
cargo build --locked --release --manifest-path operator/turn-issuer/Cargo.toml
python3 -m py_compile operator/turn-issuer/install.py operator/turn-issuer/refill.py
```

Build for the node's actual Linux architecture. The small crate keeps its own
`target/` directory; no per-task `CARGO_TARGET_DIR` is required. The packaged
Spry container must already be running as the `archipelago` user. This optional
qualification setup currently targets the separately installed
`spry-turn-lab` container; a future package migration must explicitly reconcile
that name and preserve the credential root secret.

Review the explicit hostname, public bind addresses, certificate paths and
service bounds in the configuration before installing on a different node.
Copy this directory and the reviewed Linux binary to private node scratch, then
run as the node owner:

```sh
python3 install.py install --binary ./spry-public-issuer
```

The installer refuses to replace an existing issuer. It keeps its private
receipt in `/root/archy-spry-qualification/public-issuer/receipt.json`. Its
rollback removes only this installation's listener, service, pool and firewall
rule; the existing TURN server and private dashboard remain available:

```sh
python3 /opt/archipelago/spry-public-issuer/install.py rollback
```

Keep the installer and receipt with the operator's deployment record. Do not
copy pool contents, cursor files or issued passwords into evidence or Git.

## Playback capacity

The older lab definition limited each TURN allocation to 1,000,000 payload
bytes per second across both directions. That is below a roughly 24Mb/s 4K
stream even in one direction. The controlled public-demo trial sets
8,388,608 bytes per second per allocation, keeping 32 total allocations,
eight per username, 32 client connections, one CPU and 128MiB memory.
The separate operator quadlet drop-in records that change and its rollback.
It does not update the relay binary. Aggregate throughput and useful viewer
contribution still require real device measurements; the rate configuration
alone does not prove smooth playback or network savings.
