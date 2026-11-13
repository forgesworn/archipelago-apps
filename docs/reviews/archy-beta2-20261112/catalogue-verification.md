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

## Fail-closed preparation tool

`scripts/prepare-catalogue-distribution.py` implements the required candidate
assembly without changing any trust root. For each public app it resolves the
multi-platform registry index, requires every requested architecture, replaces
the mutable tag with its immutable digest, sets the corresponding cosign claim,
and runs `cosign verify` against the operator-supplied public key. It refuses
missing images/platforms, failed signature verification and existing output.
KithMoot is excluded unless the owner/upstream explicitly selects private-OCI
delivery and supplies the archive; that archive is hashed locally and never
uploaded. The output is still unsigned and has no installation authority until
the authorised release-root holder signs it.

After the exact public images are published through the ForgeSworn `main`
workflow and their digests are cosign-signed by the authorised key holder,
prepare the candidate with:

```sh
python3 scripts/prepare-catalogue-distribution.py \
  --output .cache/app-catalog-distribution-candidate.json \
  --cosign-pubkey /etc/archipelago/cosign.pub \
  --platform linux/amd64 --platform linux/arm64 \
  --kithmoot-oci /secure/private/kithmoot-private-image.oci.tar.gz \
  --allow-private-kithmoot
```

Omit the final two arguments while the KithMoot private-distribution decision is
unresolved. The tool then produces entries only for the three public apps; it
does not silently publish or substitute KithMoot. The authorised signer, not the
agent, performs the release-root and cosign private-key operations. Once the
release-root holder has signed the catalogue, verify it with the unchanged
candidate before any installation:

```sh
archipelago ceremony verify .cache/app-catalog-distribution-candidate.json
```

On 13 November the real preflight failed closed with
`ghcr.io/forgesworn/spry:0.1.0-6b34f06-4: registry manifest unavailable (HTTP 404)`
and wrote no candidate. Six unit tests cover immutable rewriting, private-OCI
hashing/no-upload, missing authority, output preservation, required platforms
and cosign failure. Publication, private-key operations and the final signed
fresh-install rehearsal remain pending.

## Multi-platform release preparation, 13 November

The images workflow now builds and tests Wildbloom and Wildbloom Node natively
on amd64 and arm64, guards each architecture tag against replacement, and only
then creates the multi-platform tag. Wildbloom Node's existing
`0.3.5-b9a7cf4-2` amd64 tag is preserved; the multi-platform package is
`0.3.5-b9a7cf4-3`. Sales controls and payment recovery accept both package tags.
The amd64 job retains the old-version volume-upgrade check; arm64 runs the full
native smoke suite without trying to execute the old amd64-only fixture.
Corrected branch run [43525691004](https://github.com/forgesworn/archipelago-apps/actions/runs/43525691004)
passed all four native build/smoke jobs. These branch jobs did not publish.

The upstream beta frontend base URL returned 404 when the patch-level-3 build
ran. The retained unmodified upstream archive, SHA-256
`c2ef014b5ce3c660c5c0f09a552202923d1425e63610a4976745b50bd5340195`, is now
published as a [hash-pinned fallback base](https://github.com/forgesworn/archipelago-apps/releases/tag/frontend-base-v2.1.0-beta.2).
It is not a patched frontend. Frontend run
[43524870915](https://github.com/forgesworn/archipelago-apps/actions/runs/43524870915)
passed with that base and produced patch-level-3 frontend SHA-256
`92a5aba6ff9c1253ee0e3db3fb64ffeeacf9d30c78505f679b3c8939552dac70`.
Only `NATIVE-AIUI.json`, `FORGESWORN-BUNDLE.json` and `RELEASE-PAYLOAD.json`
changed from the reviewed patch-level-2 archive; all 1,277 other files are
byte-identical. The new assembled patch source is
`09c92087ca40e37a0ce881dcf4cd7e76f493f676`.

No repository signing secrets or signing workflows are configured. A read-only
check of the owner node also found no `/etc/archipelago/cosign.pub`. Therefore
there is no existing node-pinned cosign trust root to reuse, and this work must
not generate or provision one implicitly. The owner must select the cosign key
holder and provision its public key through the reviewed installation/migration
path before authenticated pulls can pass. Release-root catalogue signing and
KithMoot's private-distribution decision remain separate requirements.
