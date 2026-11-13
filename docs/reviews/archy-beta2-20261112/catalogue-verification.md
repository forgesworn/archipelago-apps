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

## Recheck, 13 November 2026

The same URL returned HTTP 200 at 10:05:57 UTC. The response was byte-identical
to the 12 November catalogue and pinned beta source: SHA-256
`ba2cbc4dafbf3c4d843ea2cac55910c279ea3b478aaf5075f64773346bb3f1b2`.
It still reports `updated: 2026-10-05`, contains 64 app entries and omits all
four integrations named above.

The independent verifier again rejected the catalogue using the source-pinned
Ed25519 root, the detached signature and the sorted compact JSON preimage. It
accepted a retained upstream `1.9.1-alpha` signed release manifest as the
positive control (SHA-256
`19dfbac51a9f266aafa6342aa1df32fc6e48b5e35a7b332a253ae2edcb49dcad`).
The beta.2 manifest URL above returned 404 during this recheck, so the earlier
beta positive-control result is retained as a dated observation rather than
represented as a fresh download.

The exact candidate binary also reproduced both outcomes in the retained
network-disabled Linux VM, with no trust-root environment override and without
starting the manager or applications:

```text
signed-manifest-control.json: verified — signed by the pinned release root
signed_by: did:key:z6Mkfu5LT8d4DjETtrkATvHh9Dvcbnr7zBCUwfau8Sw7DLWT
control_exit=0
app-catalog.json: Error: release-root signature verification failed
catalogue_exit=1
```

Candidate SHA-256 remains
`e887b68d4232523bbf48a722b906b4759e9bf3270b98cc604630d8d92f57124d`.
The VM's x86-64 compatibility loader emitted a non-fatal GLIBC weak-version
warning; both commands executed and returned the recorded statuses.

## Requested upstream resolution

1. Publish the intended current catalogue with a valid detached signature from
   the pinned release root, and confirm the unchanged `archipelago ceremony
   verify app-catalog.json` command accepts the served bytes.
2. Provide authenticated catalogue entries for `spry`, `wildbloom`,
   `wildbloom-node` and `kithmoot-node`, including compatible manifests and
   immutable image identities, or identify the supported authenticated
   distribution route for these derivative integrations. Their local unsigned
   presentation metadata is not installation authority.

After publication, each of the four apps still needs an actual installation,
start and readiness check on an isolated fresh node using the unmodified
production verifier. Until then, new-install support remains unqualified. Do
not suppress verification, add a test root or feed the modified derivative
through upstream signed OTA. Existing installed apps must remain governed by
the separately qualified preservation procedure, not catalogue absence.

## Image and signing readiness, 13 November 2026

A registry and source-path check found three further release prerequisites;
catalogue JSON alone cannot satisfy them:

1. The exact pinned Spry `ghcr.io/forgesworn/spry:0.1.0-6b34f06-4` and
   Wildbloom `ghcr.io/forgesworn/wildbloom:0.0.1-ee21ed5-5` tags return
   `manifest unknown`. PR55's Spry image jobs passed for amd64 and arm64, but
   its publication job was correctly skipped off `main`. Wildbloom Node
   `ghcr.io/forgesworn/wildbloom-node:0.3.5-b9a7cf4-2` is available, currently
   as an amd64 image. The older published Spry `…-3` and Wildbloom `…-4`
   packages are not substitutes: the candidate changes their bundled NIP-07
   providers, which is why their package revisions increased.
2. Beta's pull choke points require both an immutable
   `registry/repository@sha256:…` reference and an `image_signature` claim.
   Cosign must verify that exact digest using the node's pinned
   `/etc/archipelago/cosign.pub`; TLS verification cannot be disabled. This is
   independent of the catalogue's Ed25519 release-root signature. The three
   public app manifests currently have mutable tag references and no image
   signature claim, so an entry copied verbatim from them would still fail at
   pull time.
3. KithMoot Node is deliberately outside `apps/`. Its documented distribution
   is a private OCI import using `localhost/kithmoot-node:…` and
   `pull_policy: never`; Shelter is a private input. A public registry/catalogue
   entry would change that chosen position and is not authorised by this
   engineering check. A supported route therefore needs an explicit owner and
   upstream decision covering private image delivery as well as signing.

Before App Store qualification, publish the exact reviewed public images under
their unused pinned tags (without replacing an existing tag), resolve and cosign
their immutable multi-platform digests, embed those references and claims in the
compatible manifests, and have the authorised release-root holder sign the
complete catalogue. Then rerun the unchanged verifier and actual isolated
fresh-install checks. For KithMoot, first agree whether authenticated private
OCI delivery or another supported route is intended; do not silently publish
Shelter or the private image.

## Local application installation rehearsal, 13 November 2026

A separate clean Debian 13 guest used the exact reviewed ARM64 backend
`9a5fde6fc0555f3675f052b9e3d8a141bda21e7b4f0e5bf94256a17b97deb5b7`
and frontend `75eb02bab32700e73b038fb5fabe57118b9a36972be7ff43c3b080804f53f19d`.
Through actual authenticated manager RPCs and rootless Podman, it installed,
started and readiness-checked Wildbloom Node, Wildbloom, Spry and KithMoot Node.
All four remained running on independent readback. Spry reported its private
relay ready; both Wildbloom containers reported healthy. KithMoot matched the
exact retained private image ID
`bc57a79baf111d3e2bc4a5c2c15bebb91c96469bca96dda49ceb32d51461cd86`
and executed through Rosetta. The public [evidence receipt](fresh-apps-local-evidence.json)
contains the other local image IDs and scope flags.

The three public images were built from the candidate's pinned ARM64 inputs;
Wildbloom Node's build also passed its application and Shelter test stages. The
private KithMoot OCI contained code only, not restored room or identity state.
External routing was removed before seed onboarding and stayed absent through
all four installs. The fixture used generated credentials, a loopback-only
dummy public address and self-signed public certificate for KithMoot preflight,
plus the release-checksummed ARM64 FIPS package omitted by the lite recipe. It
made no payment and no external client or network claim.

This proves local application installability only. Images were loaded directly
and manifests staged locally, so no release-root catalogue, registry pull,
immutable digest or cosign verification was exercised. The first run also found
that `install-lite.sh` omitted `nftables`, causing `archy-net` creation to fail;
the installer now includes it, its regression passes, and the clean rerun used
the corrected bundle without mid-run repair. `tests/node/fresh-apps-host.py`
is the guarded fixture driver. The final signed-distribution rehearsal remains
necessary after the publication decisions above.
