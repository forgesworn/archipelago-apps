// Adapted from Wildbloom a7f79cb scripts/services-acceptance.mjs (MIT).
// Linux-only: published images, real loopback TLS, synthetic receiving services.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { once } from "node:events";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer, request } from "node:http";
import { createServer as createHttpsServer } from "node:https";
import { pathToFileURL } from "node:url";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { finalizeEvent, getPublicKey, verifyEvent } from "nostr-tools/pure";
import { chromium } from "playwright-core";
import { WebSocketServer } from "ws";
import AxeBuilder from "@axe-core/playwright";
const source = process.env.WILDBLOOM_SOURCE_DIR;
assert.ok(source, "Set WILDBLOOM_SOURCE_DIR to the pinned Wildbloom checkout.");
const { assertNoBrowserPersistence, installBrowserPersistenceAudit } =
  await import(pathToFileURL(join(source, "scripts/browser-persistence.mjs")));
const { runPreflight } =
  await import(pathToFileURL(join(source, "scripts/checkout-preflight.mjs")));

// Public synthetic keys stay in this harness, never enter application code.
const key = new Uint8Array(32).fill(42),
  pubkey = getPublicKey(key);
const fixture = process.env.WILDBLOOM_CHECKOUT_FIXTURE;
const [nodeTag, appTag] = process.argv.slice(2);
assert.ok(fixture && nodeTag && appTag, "Pass Node and app image tags and set WILDBLOOM_CHECKOUT_FIXTURE.");
assert.equal(process.platform, "linux", "Run on Linux: containers share the fixture's loopback network.");
const docker = (...args) => execFileSync("docker", args, { encoding: "utf8" }).trim();
function pinnedImage(tag) {
  const metadata = JSON.parse(docker("image", "inspect", tag))[0];
  const digest = metadata.RepoDigests?.find(d => d.startsWith(tag.split(":")[0] + "@"));
  assert.ok(digest, "Pull the published image first; local rebuilds are not release acceptance.");
  return { tag, digest, id: metadata.Id };
}
const build = { node: pinnedImage(nodeTag), app: pinnedImage(appTag) };
const tls = {
  key: readFileSync(process.env.WILDBLOOM_TEST_TLS_KEY),
  cert: readFileSync(process.env.NODE_EXTRA_CA_CERTS),
};
const servers = new Set();
const containers = new Set();
async function tlsProxy(listenPort, targetPort) {
  const server = createHttpsServer(tls, (req, res) => {
    const upstream = request({ hostname: "127.0.0.1", port: targetPort,
      method: req.method, path: req.url, headers: req.headers }, response => {
      res.writeHead(response.statusCode, response.headers);
      response.pipe(res);
    });
    upstream.on("error", () => { res.writeHead(502); res.end(); });
    req.pipe(upstream);
  });
  servers.add(server);
  server.listen(listenPort, "127.0.0.1");
  await once(server, "listening");
}
const root = mkdtempSync(join(tmpdir(), "wildbloom-services-"));
const children = new Set();
let browser, relay, activePage;
const faults = [];
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
async function port() {
  const s = createServer();
  s.listen(0, "127.0.0.1");
  await once(s, "listening");
  const p = s.address().port;
  await new Promise((r) => s.close(r));
  return p;
}
function launch(cmd, args) {
  const c = spawn(cmd, args, { stdio: "ignore" });
  children.add(c);
  c.on("error", () => faults.push("Child failed to start"));
  return c;
}
async function stop(c) {
  if (c.exitCode !== null || c.signalCode !== null) return;
  const done = once(c, "exit");
  c.kill("SIGTERM");
  const t = setTimeout(() => c.kill("SIGKILL"), 5000);
  try {
    await done;
  } finally {
    clearTimeout(t);
  }
}
async function ready(c, origin, path = "/") {
  for (let i = 0; i < 200; i++) {
    assert.equal(c.exitCode, null, "Service exited before readiness");
    try {
      if ((await fetch(origin + path, { signal: AbortSignal.timeout(500) })).ok)
        return;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw Error("Service readiness timed out");
}
async function wait(page, text) {
  await page
    .locator("#node-service-status")
    .filter({ hasText: text })
    .waitFor();
}
async function sign(page, kind) {
  await page.waitForFunction((k) => {
    try {
      return (
        JSON.parse(document.querySelector("#external-unsigned-event").value)
          .kind === k
      );
    } catch {
      return false;
    }
  }, kind);
  const t = JSON.parse(await page.inputValue("#external-unsigned-event"));
  const e = finalizeEvent(t, key);
  await page.fill("#external-signed-event", JSON.stringify(e));
  await page.click("#accept-external-signature");
  return e;
}
async function action(page, id, kind = 27235) {
  await page.click(id);
  return sign(page, kind);
}
async function download(page, selector) {
  const promise = page.waitForEvent("download");
  await page.locator(selector).click();
  return readFileSync(await (await promise).path());
}
function uploadAuth(bytes, origin) {
  const now = Math.floor(Date.now() / 1000);
  return (
    "Nostr " +
    Buffer.from(
      JSON.stringify(
        finalizeEvent(
          {
            kind: 24242,
            created_at: now,
            content: "Synthetic acceptance upload",
            tags: [
              ["t", "upload"],
              ["x", hash(bytes)],
              ["server", new URL(origin).hostname],
              ["expiration", String(now + 60)],
            ],
          },
          key,
        ),
      ),
    ).toString("base64")
  );
}
try {
  const appOrigin = `https://127.0.0.1:${await port()}`,
    nodeOrigin = "https://127.0.0.1:3742",
    nodePort = await port(),
    mintOrigin = `http://127.0.0.1:${await port()}`;
  const mint = launch(fixture, [new URL(mintOrigin).port]);
  await ready(mint, mintOrigin);
  const info = await (await fetch(mintOrigin)).json();
  const destination = {
    origin: mintOrigin + "/",
    addresses: [new URL(mintOrigin).host],
    allow_loopback_http: true,
  };
  const password = join(root, "password");
  writeFileSync(password, "synthetic-limited-password", { mode: 0o600 });
  const profile = join(root, "profile.json");
  writeFileSync(
    profile,
    JSON.stringify({
      checkout: {
        origin: nodeOrigin + "/",
        seller_id: "synthetic",
        seller_name: "Synthetic operator",
        network: "bitcoin",
        quote_seconds: 600,
        allow_loopback_http: true,
        tor_only: false,
        offers: [
          {
            id: "small",
            revision: 1,
            capacity_bytes: 1024 * 1024,
            duration_seconds: 3600,
            grace_seconds: 60,
            price_msat: 10000,
            delivery_bytes: 1024 * 1024,
            delivery_policy: "Synthetic operator-managed delivery",
            retention_policy: "One hour plus grace",
            refund_policy: "Contact synthetic operator",
          },
        ],
        issuers: [
          {
            id: "fixture",
            note_endpoint: mintOrigin + "/w",
            callback: mintOrigin + "/callback",
            mint_pubkey: info.mint_pubkey,
          },
        ],
      },
      max_paid_bytes: 1024 * 1024,
      state: join(root, "node", "operator", "checkout"),
      browser_origins: [appOrigin],
      phoenixd: { destination, password_file: password },
      notes: [
        { endpoint: mintOrigin + "/w", destination },
        { endpoint: mintOrigin + "/callback", destination },
      ],
    }),
    { mode: 0o600 },
  );
  const args = [
    "--no-tor",
    "--bind",
    `127.0.0.1:${nodePort}`,
    "--public-url",
    nodeOrigin,
    "--data-dir",
    join(root, "node"),
    "--repair-interval",
    "0",
    "--checkout-profile",
    profile,
    "--storage-proofs",
    "--quota-bytes", "2097152",
  ];
  function startNode() {
    const name = `archy-services-node-${process.pid}`;
    containers.add(name);
    return launch("docker", ["run", "--rm", "--name", name, "--network", "host",
      "--cap-drop=ALL", "--security-opt=no-new-privileges", "--read-only",
      "--tmpfs", "/tmp", "--user", `${process.getuid()}:${process.getgid()}`, "-v", `${root}:${root}`, build.node.digest, ...args]);
  }
  async function stopNode(child) {
    docker("stop", "--time", "5", `archy-services-node-${process.pid}`);
    await stop(child);
  }
  let node = startNode();
  await tlsProxy(3742, nodePort);
  await ready(node, nodeOrigin);
  const checkoutReadiness = await runPreflight({
    node: nodeOrigin, app: appOrigin, offer: "small", rail: "lightning", maxSats: 10,
  });
  assert.equal(checkoutReadiness.status, "preflight-passed");
  assert.equal(checkoutReadiness.paymentAttempted, false);
  const unpaid = Buffer.from("unpaid synthetic upload");
  const denied = await fetch(nodeOrigin + "/upload", {
    method: "PUT",
    headers: {
      Authorization: uploadAuth(unpaid, nodeOrigin),
      "Content-Type": "application/octet-stream",
      "X-SHA-256": hash(unpaid),
    },
    body: unpaid,
  });
  assert.equal(denied.ok, false, "Unpaid signer has no upload authority");
  const relayServer = createHttpsServer(tls);
  servers.add(relayServer);
  relay = new WebSocketServer({ server: relayServer });
  relayServer.listen(0, "127.0.0.1");
  await once(relayServer, "listening");
  const relayUrl = `wss://127.0.0.1:${relayServer.address().port}/`;
  const list = finalizeEvent(
    {
      kind: 10063,
      created_at: Math.floor(Date.now() / 1000),
      content: "",
      tags: [["server", nodeOrigin + "/"]],
    },
    key,
  );
  const publications = [];
  relay.on("connection", (s) =>
    s.on("message", (b) => {
      const m = JSON.parse(b);
      if (m[0] === "REQ") {
        if (m[2].kinds?.includes(10063))
          s.send(JSON.stringify(["EVENT", m[1], list]));
        s.send(JSON.stringify(["EOSE", m[1]]));
      }
      if (m[0] === "EVENT") {
        assert.ok(verifyEvent(m[1]));
        publications.push(m[1]);
        s.send(JSON.stringify(["OK", m[1].id, true, "stored"]));
      }
    }),
  );
  const appName = `archy-services-app-${process.pid}`;
  containers.add(appName);
  docker("run", "-d", "--name", appName, "--security-opt=no-new-privileges",
    "-p", "127.0.0.1::3743", "-e", `WILDBLOOM_HOME_NODE_URL=${nodeOrigin}`, build.app.digest);
  const appPort = Number(docker("port", appName, "3743/tcp").split(":").at(-1));
  await tlsProxy(Number(new URL(appOrigin).port), appPort);
  await ready({ exitCode: null }, appOrigin);
  browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.WILDBLOOM_BROWSER_EXECUTABLE ??
      (process.platform === "darwin"
        ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        : "/usr/bin/google-chrome"),
  });
  // Only this isolated browser trusts the ephemeral loopback certificate.
  const context = await browser.newContext({ acceptDownloads: true, ignoreHTTPSErrors: true });
  await context.addInitScript(installBrowserPersistenceAudit);
  const page = await context.newPage();
  activePage = page;
  page.setDefaultTimeout(20000);
  const requests = [];
  page.on("pageerror", (e) => faults.push(e.message));
  await page.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    requests.push(u.href);
    if (![appOrigin, nodeOrigin].includes(u.origin)) {
      faults.push("Unexpected browser origin");
      await route.abort();
    } else await route.continue();
  });
  await page.goto(appOrigin + "/#client");
  await page.locator("#connect-signer").waitFor();
  assert.ok(requests.every((u) => new URL(u).origin === appOrigin));
  await page.fill("#relay-urls", relayUrl);
  await page.locator("#archipelago-use-node").waitFor();
  assert.equal(await page.inputValue("#blossom-server"), nodeOrigin, "Packaged own-node default");
  await page.check('input[name="signing-method"][value="external"]');
  await page.fill("#external-signer-pubkey", pubkey);
  await page.click("#connect-signer");
  await page
    .locator('section[aria-labelledby="node-services-heading"] details')
    .evaluateAll((elements) => elements.forEach((e) => (e.open = true)));
  await page.fill("#discovery-keys", pubkey);
  const before = requests.filter((u) => u.startsWith(nodeOrigin)).length;
  await page.click("#discover-nodes");
  await wait(page, "Found 1 nodes");
  assert.equal(
    requests.filter((u) => u.startsWith(nodeOrigin)).length,
    before,
    "Discovery must not probe nodes",
  );
  await page.click("#discovery-results button");
  assert.equal(await page.inputValue("#blossom-server"), nodeOrigin + "/");
  await page.check("#list-public-consent");
  await action(page, "#publish-server-list", 10063);
  await wait(page, "Server list accepted");
  assert.equal(publications.length, 1);
  await page.click("#checkout-offers");
  await wait(page, "Offers loaded");
  await action(page, "#checkout-quote");
  await wait(page, "Quote reserved");
  const reference = JSON.parse(
    (await download(page, "#checkout-receipt-links a")).toString(),
  );
  await page.check("#checkout-consent");
  await action(page, "#checkout-pay");
  await wait(page, "awaiting_payment");
  assert.match(
    await page.locator("#checkout-payment a").getAttribute("href"),
    /^lightning:lnbc/u,
  );
  await action(page, "#checkout-check");
  await wait(page, "awaiting_payment");
  await fetch(mintOrigin + "/fixture/pay", { method: "POST" });
  // Exercise the packaged local recovery binary against the original invoice.
  // The wrapper's process/backup failures are tested separately in Python.
  await stopNode(node);
  const runtimeProfile = JSON.parse(readFileSync(profile, "utf8"));
  const recoveryProfile = join(root, "recovery.json");
  writeFileSync(recoveryProfile, JSON.stringify({ checkout: runtimeProfile.checkout,
    phoenixd: runtimeProfile.phoenixd, notes: runtimeProfile.notes,
    storage_root: join(root, "node"), quota_bytes: 2097152, max_blob_bytes: 1073741824 }), { mode: 0o600 });
  const pendingInventory = JSON.parse(execFileSync(process.env.WILDBLOOM_SALES_READER, [join(root, "node")], { encoding: "utf8" }));
  const pendingOrder = pendingInventory.orders.find(o => o.state === "awaiting_payment");
  assert.ok(pendingOrder);
  const reconcile = () => docker("run", "--rm", "--network", "host", "--user", `${process.getuid()}:${process.getgid()}`,
    "-v", `${root}:${root}`, "--entrypoint", "/usr/local/bin/checkout-operator", build.node.digest,
    "--state", join(root, "node", "operator", "checkout"), "reconcile", pendingOrder.order_id, "--profile", recoveryProfile);
  assert.equal(JSON.parse(reconcile()), "active");
  assert.equal(JSON.parse(reconcile()), "active", "Repeated local recovery must return the original activation");
  node = startNode();
  await ready(node, nodeOrigin);
  await action(page, "#checkout-check");
  await wait(page, "active");
  const stranger = new Uint8Array(32).fill(43);
  async function assertCapacityFull(requestId) {
    const url = nodeOrigin + "/checkout/v1/orders";
    const body = JSON.stringify({ request_id: requestId, offer_id: "small", rail: "lightning", renews: null });
    const event = finalizeEvent({ kind: 27235, created_at: Math.floor(Date.now() / 1000), content: "",
      tags: [["u", url], ["method", "POST"], ["payload", hash(body)]] }, stranger);
    const response = await fetch(url, { method: "POST", body,
      headers: { "content-type": "application/json", authorization: "Nostr " + Buffer.from(JSON.stringify(event)).toString("base64") } });
    assert.equal(response.status, 503, "Packaged aggregate paid ceiling refuses another buyer");
    await response.arrayBuffer();
  }
  await assertCapacityFull("before-restart");
  assert.equal(
    (await (await fetch(mintOrigin)).json()).invoice_creations,
    1,
    "No replacement invoice on a check",
  );
  await assertNoBrowserPersistence(page, context, "Before restart");
  await stopNode(node);
  node = startNode();
  await ready(node, nodeOrigin);
  await page.reload();
  await page.locator("#connect-signer").waitFor();
  await page.locator("#archipelago-use-node").waitFor();
  assert.equal(await page.inputValue("#blossom-server"), nodeOrigin, "Packaged own-node default");
  await page.check('input[name="signing-method"][value="external"]');
  await page.fill("#external-signer-pubkey", pubkey);
  await page.click("#connect-signer");
  await page
    .locator('section[aria-labelledby="node-services-heading"] details')
    .evaluateAll((es) => es.forEach((e) => (e.open = true)));
  await page.fill("#checkout-reference", JSON.stringify(reference));
  await action(page, "#checkout-recover");
  await wait(page, "Recovered order: active");
  await assertCapacityFull("after-restart");
  await page.setInputFiles("#publish-file", {
    name: "private-storage.bin",
    mimeType: "application/octet-stream",
    buffer: Buffer.alloc(65539, 73),
  });
  await page.click("#inspect-file");
  await page
    .locator("#publish-status")
    .filter({ hasText: "Encrypted transfer payload prepared" })
    .waitFor();
  await page.check("#key-saved-consent");
  await page.check("#upload-consent");
  await action(page, "#upload-file", 24242);
  await page
    .locator("#publish-status")
    .filter({ hasText: "Blossom metadata is staged" })
    .waitFor();
  await page.click("#sign-events");
  assert.equal(await page.locator("#sign-events").isDisabled(), true);
  assert.match(await page.locator("#publish-status").textContent(), /waiting for an external signature/);
  const fileEvent = await sign(page, 1063);
  await page
    .locator("#publish-status")
    .filter({ hasText: "Exact external signatures accepted" })
    .waitFor();
  await stopNode(node);
  node = startNode();
  await ready(node, nodeOrigin);
  await assertCapacityFull("after-paid-upload-restart");
  await page
    .locator("#saved-event-json")
    .evaluate((e) => (e.closest("details").open = true));
  await page.fill("#saved-event-json", JSON.stringify(fileEvent));
  await page.click("#verify-saved-event");
  await page.check("#proof-consent");
  await page.click("#storage-audit");
  await wait(page, "waiting for HTTP-auth approval");
  await sign(page, 27235);
  await wait(page, "All selected targets passed");
  const audit = JSON.parse(
    (await download(page, "#storage-audit-results a")).toString(),
  );
  assert.equal(audit.proofs.length, 1);
  assert.equal(audit.failed.length, 0);
  const blobHash = fileEvent.tags.find((t) => t[0] === "x")[1];
  const blobPath = join(root, "node", "blobs", blobHash.slice(0, 2), blobHash);
  const original = readFileSync(blobPath);
  writeFileSync(blobPath, Buffer.alloc(original.length));
  await action(page, "#storage-audit");
  await wait(page, "Some targets could not be verified");
  const failedAudit = JSON.parse((await download(page, "#storage-audit-results a")).toString());
  assert.equal(failedAudit.failures.length, 1);
  assert.equal(failedAudit.failures[0].sha256, blobHash);
  assert.ok(["http", "retrieval"].includes(failedAudit.failures[0].stage));
  assert.ok((await page.locator("#storage-audit-results").textContent()).includes(failedAudit.failures[0].reason));
  writeFileSync(blobPath, original);
  await page.click("#checkout-offers");
  await wait(page, "Offers loaded");
  await page.selectOption("#checkout-rail", "lnurlcash");
  await page.fill("#checkout-renews", reference.order_id);
  await page.locator("#checkout-renews").dispatchEvent("change");
  await action(page, "#checkout-quote");
  await wait(page, "Quote reserved");
  await download(page, "#checkout-receipt-links a");
  await page.check("#checkout-consent");
  await page.fill("#checkout-note", mintOrigin + "/w?k1=" + "06".repeat(32));
  await action(page, "#checkout-pay");
  await wait(page, "active");
  assert.equal(await page.inputValue("#checkout-note"), "");
  assert.equal((await (await fetch(mintOrigin)).json()).note_rotations, 1);
  await stopNode(node);
  node = startNode();
  await ready(node, nodeOrigin);
  await action(page, "#checkout-check");
  await wait(page, "active");
  assert.equal((await (await fetch(mintOrigin)).json()).note_rotations, 1, "Restart/check must not rotate the note again");
  await assertCapacityFull("after-renewal");
  assert.ok(process.env.WILDBLOOM_SALES_READER, "Set WILDBLOOM_SALES_READER to the dashboard projection fixture");
  const inventory = JSON.parse(execFileSync(process.env.WILDBLOOM_SALES_READER, [join(root, "node")], { encoding: "utf8" }));
  assert.equal(inventory.summary.paid_orders, 2);
  assert.equal(inventory.summary.retained_customers, 1);
  assert.equal(inventory.summary.allocated_bytes, 1024 * 1024);
  const activated = inventory.orders.filter(order => order.state === "active");
  assert.equal(activated.length, 2);
  // The daemon journals before reserving capacity. The four refused buyers'
  // requests remain reserving; viewing them must not turn them into purchases.
  assert.equal(inventory.orders.filter(order => order.state === "reserving").length, 4);
  assert.equal(inventory.summary.needs_attention, 4);
  assert.deepEqual(activated[0].allowance, activated[1].allowance, "Renewal shares the latest allowance dates");
  assert.equal(activated[0].allowance.status, "active");
  for (const order of inventory.orders) {
    for (const forbidden of ["invoice", "rotation", "payment_hash", "settlement", "note_id"]) assert.equal(forbidden in order, false);
  }
  assert.equal((await (await fetch(mintOrigin)).json()).note_rotations, 1, "Dashboard read must not contact the receiver");
  // Record an explicitly synthetic completed refund; never send any money.
  const refunded = JSON.parse(execFileSync(process.env.WILDBLOOM_SALES_READER,
    [join(root, "node"), "--record-refund", activated[0].order_id, String(activated[0].price_msat), "cd".repeat(32)], { encoding: "utf8" }));
  const savedRefund = refunded.orders.find(o => o.order_id === activated[0].order_id);
  assert.equal(savedRefund.refund.amount_msat, activated[0].price_msat);
  assert.equal(savedRefund.refund.payment_hash, "cd".repeat(32));
  assert.deepEqual(savedRefund.allowance, activated[0].allowance);
  assert.equal(savedRefund.state, "active");
  assert.equal((await (await fetch(mintOrigin)).json()).note_rotations, 1, "Refund record must not contact receiver");
  const retried = JSON.parse(execFileSync(process.env.WILDBLOOM_SALES_READER,
    [join(root, "node"), "--record-refund", activated[0].order_id, String(activated[0].price_msat), "cd".repeat(32)], { encoding: "utf8" }));
  assert.deepEqual(retried.orders.find(o => o.order_id === activated[0].order_id).refund, savedRefund.refund);
  assert.equal(publications.length, 1, "No payment or proof events published");
  await assertNoBrowserPersistence(page, context, "Node services");
  const axe = await new AxeBuilder({ page })
    .include('section[aria-labelledby="node-services-heading"]')
    .analyze();
  assert.deepEqual(axe.violations, []);
  assert.deepEqual(faults, []);
  console.log(
    JSON.stringify(
      {
        version: 1,
        result: "passed",
        build,
        checks: [
          "dashboard read-only sales projection of the live packaged ledger and renewed allowance",
          "idempotent private operator refund record on packaged orders without receiving I/O or allowance changes",
          "published images resolved and run by digest",
          "packaged own-node default before checkout and after reload",
          "paid-capacity ceiling before/after restart and renewal without double counting",
          "explicit trusted discovery without node probes",
          "public list exact signing",
          "unpaid upload refused",
          "Lightning quote-invoice-check-activation",
          "one invoice across checks",
          "daemon restart and private order recovery",
          "packaged operator reconciles the original invoice and repeated reconciliation preserves activation",
          "paid encrypted upload and full-read retrieval after restart",
          "fresh full-read proof",
          "corruption refusal",
          "LNURLcash exact-value rotation and activation",
          "no payment/proof relay publication",
          "no browser persistence",
          "service controls accessibility",
        ],
        limits:
          "Synthetic receiving backends, Chromium and one host; no real-money settlement or independent storage-custody proof.",
      },
      null,
      2,
    ),
  );
} catch (error) {
  if (activePage)
    console.error(
      JSON.stringify({
        publish: await activePage.locator("#publish-status").textContent(),
        service: await activePage.locator("#node-service-status").textContent(),
      }),
    );
  throw error;
} finally {
  await browser?.close();
  for (const name of containers) {
    try { docker("rm", "-f", name); } catch { /* --rm may already have removed it */ }
  }
  for (const c of children) await stop(c);
  if (relay) await new Promise((r) => relay.close(r));
  for (const server of servers) {
    server.closeAllConnections();
    await new Promise(r => server.close(r));
  }
  rmSync(root, { recursive: true, force: true });
}
