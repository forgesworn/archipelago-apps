// Build a BUD-01 Blossom authorisation event (kind 24242) and print it base64-encoded.
// Usage: node sign-auth.mjs <secret-hex> <upload|get|delete> <sha256> <server-name>
import { finalizeEvent } from "nostr-tools/pure";
import { hexToBytes } from "nostr-tools/utils";

const [secretHex, verb, sha256, serverName] = process.argv.slice(2);
if (!secretHex || !verb || !sha256 || !serverName) {
  console.error("usage: sign-auth.mjs <secret-hex> <verb> <sha256> <server-name>");
  process.exit(2);
}
const now = Math.floor(Date.now() / 1000);
const event = finalizeEvent(
  {
    kind: 24242,
    created_at: now,
    content: `${verb} ${sha256}`,
    tags: [["t", verb], ["x", sha256], ["expiration", String(now + 300)], ["server", serverName]],
  },
  hexToBytes(secretHex),
);
process.stdout.write(Buffer.from(JSON.stringify(event)).toString("base64"));
