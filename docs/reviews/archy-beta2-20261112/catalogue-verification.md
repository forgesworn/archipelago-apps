# Catalogue verification for upstream review

Prepared for the owner to share; no maintainer has been contacted.

On 12 November 2026, the public `releases/app-catalog.json` was rejected by
both an independent Ed25519 verifier and the exact retained beta derivative's
production verifier. The same binary accepted the beta release manifest as a
positive control. Neither check used a test root or signing mnemonic.

Source:
https://source.archipelago-foundation.org/lfg2025/archy/raw/branch/main/releases/app-catalog.json

Catalogue SHA-256:
`ba2cbc4dafbf3c4d843ea2cac55910c279ea3b478aaf5075f64773346bb3f1b2`.
It is byte-identical to the catalogue in pinned beta source
`5aac0d20571e6f673b8a5df95a5c8fcab2932c39`.

Release-manifest source:
https://source.archipelago-foundation.org/lfg2025/archy/releases/download/v2.1.0-beta.2/manifest.json

Release-manifest file SHA-256:
`59234917bd97a1f89dc7d5b77292d08fa40a4c7d3b085b82b1cf9b276b2eabe0`.

Run with the retained candidate binary (SHA-256
`e887b68d4232523bbf48a722b906b4759e9bf3270b98cc604630d8d92f57124d`)
in an isolated Linux environment, with the two downloaded files:

```sh
./archipelago ceremony verify manifest.json
./archipelago ceremony verify app-catalog.json
```

Observed results:

```text
manifest.json: verified — signed by the pinned release root
signed_by: did:key:z6Mkfu5LT8d4DjETtrkATvHh9Dvcbnr7zBCUwfau8Sw7DLWT
app-catalog.json: Error: release-root signature verification failed
```

The binary was executed in a disposable, read-only, network-disabled Debian 13
container with no capabilities and only read-only mounts of the binary and
these public documents. The container and task-created base image were removed.

Expected: the intended current catalogue passes the compiled release-root
verifier. Separately, there are no `spry`, `wildbloom`, `wildbloom-node` or
`kithmoot-node` entries in the fetched catalogue. Those need an agreed,
authenticated distribution route before new App Store installation is qualified.
This does not establish a reason to remove existing installed apps.
