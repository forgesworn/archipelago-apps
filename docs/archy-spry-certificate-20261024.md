# Spry certificate selection qualification

24 October 2026. Operator-only follow-up to the invited public qualification.

`node/expose-spry-lab.py certificate --lineage NAME` now selects an existing
operator certificate lineage. It validates the lineage label, hostname,
remaining lifetime and certificate/key match, backs up the current files
privately on the node, restarts Spry and checks the pinned runtime. Failure
restores the prior files. Renewal follows the selected lineage and ignores
unrelated renewal hooks. Restarting discards existing TURN allocations.
The dashboard certificate, transport secret, firewall and image are unchanged
by this operation. The focused Python suite passed all 34 tests.

A separately issued trusted RSA certificate did not resolve the Android
client's missing TLS relay candidates. Browser TLS succeeded, and the
physical GrapheneOS call succeeded with native TCP and browser TLS. This is
not evidence of native TLS acceptance or a confirmed TLS root cause.

The original operator certificate was restored. The temporary lineage,
its additional private-key backup and the nine temporary qualification
profiles were removed. The previous original-certificate backup remains
root-private for rollback. Final runtime readback confirmed the pinned
image, read-only root filesystem, no container log driver, 128 MiB memory
limit, one CPU and loopback peers refused. Host/provider logging was not
audited by that check.

No discovery, public credential issuer or mandatory client default was
introduced. This qualifies Spry/WebRTC; it does not implement RelaySwarm or
Sapflow real-time group forwarding or establish an OSA exemption.
