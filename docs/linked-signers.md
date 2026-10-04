# Linked signers

A linked identity is an Archipelago identity whose Nostr key lives in a NIP-46
remote signer, not on the node. Apps use it like any other identity: pick it
in the dashboard's identity picker, and sign or encrypt through the usual
NIP-07 bridge. The node forwards each request to the signer over a Nostr relay
and checks every signed event before an app sees it: the signer's key, the
kind, tags, content and time requested, the event id and the signature.

This needs backend `-p4` or later (`upstream/patches/0003` to `0005`).

## Why you'd want one

The node is always on, reachable over the network, and runs third-party apps.
With a linked identity, the node can ask for a signature but never holds the
key. A hardware signer can also show what it's signing and wait for your
approval.

## Signers that work

Any NIP-46 signer works. There are two ways to pair:

- **`bunker://` link from the signer**, for example Heartwood (from
  Sapwood) or Signet Lite:

  ```sh
  read -rs ARCHY_PASSWORD; export ARCHY_PASSWORD
  scripts/link-signer.sh --name "Heartwood" --purpose personal
  # paste the bunker:// link when asked
  ```

- **`nostrconnect://` link from the node**, which the signer scans or pastes.
  Use this with My Signet, Amber, Archipelago's companion app or Signet Lite.
  Pass relays the signer's device can reach:

  ```sh
  scripts/link-signer.sh --nostrconnect --relay wss://relay.example.com --name "Phone"
  ```

  The script prints the link, and a QR code if `qrencode` is installed. It
  then waits up to 5 minutes for the signer to connect.

Either way, the node then asks the signer to sign a one-off challenge, which
proves the signer really holds the key. Approve it on the signer if it asks.
Some signers (Signet Lite among them) accept a `bunker://` link only once, so
create a fresh one if a link attempt fails.

Apps that take the owner list from `{{NODE_IDENTITY_PUBKEYS}}`, such as
`wildbloom-node`, pick up a newly linked key when they restart: press
**Restart** on the app in the dashboard after linking.

### Heartwood

Heartwood is a hardware signer that runs on an ESP32 board. Its keys stay on
the board, and its button and policy engine gate every signature.

- **WiFi-standalone mode** is the simplest: the board connects to a relay by
  itself, so the node needs nothing extra. Link it with its `bunker://` link
  from Sapwood, keeping only the first `relay=`: the board answers on that
  relay alone. Its approvals time out after about 30 s.
- **USB through a bridge**: the board's radio stays off, and
  `heartwood-bridge` talks to it over USB serial. If you enable the node's
  mesh-radio feature with auto-detect, the node also probes every
  `ttyUSB*`/`ttyACM*` port, which can include the Heartwood. Pin the mesh
  radio to its own device path, or leave mesh off.

## Logging in with your signer

With backend `-p5` and frontend `-p1` or later (`upstream/patches/0006` and
`0007`), a linked identity can also log you in to the dashboard. Your password
always keeps working.

- **Enrol it:** Settings → Security, "Add a login signer", or the optional
  "Connect a signer" step at the end of onboarding. You confirm your password,
  the page shows a 4-digit code, and you approve on the signer once it shows
  the same code.
- **Log in:** "Log in with your signer" on the login page. The page shows a
  code; check your signer shows the same one, then approve. If your signer
  asks when you didn't start a login on this page, deny it.
- **With 2FA:** enter your password first, then choose "Approve on your
  signer instead" in place of the authenticator code.
- **Heartwood:** firmware with login-challenge support (Heartwood PR #210 and
  later) always asks for the button on a login, even on a pairing set to
  approve automatically, and shows "LOG IN" with the code. A signer that
  approves logins automatically makes signer login only as strong as that
  signer: the dashboard warns you at enrolment if the approval came back too
  fast for a person.
- **Dashboard address:** signer login and enrolment work when you reach the
  dashboard on port 80 or 443. On any other port, log in with your password.
- **Someone else trying:** each login waits for one approval at a time, and a
  burst of attempts pauses signer login for a while. Logging in with your
  password lifts the pause, and Settings → Security lists recent attempts with
  their addresses.

## Limits

- **The signer has to be online.** A request to a signer that doesn't answer
  fails with `linked signer is offline` within about 10 s: the node pings the
  signer first if it has been quiet for 30 s, and otherwise when a request
  goes unanswered for 5 s. A slow relay in the link doesn't hold a reply up. A signer that answers the
  ping but is waiting for you to approve gets up to 60 s.
- **A signer that restarts** and forgets the node is paired again on the next
  request, using the secret from the original link.
- **Approve promptly.** The dashboard gives up on a request after about 15 s
  and retries, for about 47 s in all. The node merges those retries into one
  request, so you see one prompt, but an approval slower than that reaches the
  app as a timeout. Heartwood's policy engine can approve trusted apps
  automatically.
- **Full events only.** A linked identity refuses requests to sign a bare
  event hash, because the signer couldn't show you what it's approving.
- **Removing a link:** delete the identity in the dashboard. That removes the
  node's pairing keys; revoke the node's client on the signer too.
- **Linking happens from a script.** There's no dashboard screen for it yet
  (see `upstream-notes.md`).
