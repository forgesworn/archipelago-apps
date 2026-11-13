// Component review only. API signatures use the real controller; the node
// adapter and Archy signer are fixtures. Host/TURN integration is separate.
import assert from 'node:assert/strict'
import { request } from 'node:http'
import { mkdir, writeFile, readFile, readdir, unlink } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../tests/smoke/node_modules/playwright-core/index.mjs'
import AxeBuilder from '../../tests/smoke/node_modules/@axe-core/playwright/dist/index.mjs'
import { generateSecretKey, getPublicKey, finalizeEvent } from 'nostr-tools/pure'
import QRCode from 'qrcode'
import { createController } from './server.mjs'
import { Refused } from './private-state.mjs'
import { pickLimits } from './limits.mjs'
import { dashboardSnapshot, healthReport, checkNames } from './observability.mjs'

assert.equal(process.env.E2E_KITHMOOT_NODE_UI, 'component-review')
const directory = process.env.E2E_KITHMOOT_NODE_REVIEW_OUTPUT || fileURLToPath(new URL('../../docs/evidence/kithmoot-node-settings-metrics-20261105/', import.meta.url))
await mkdir(directory, { recursive: true })
const sourceNames = ['client.mjs', 'dashboard.mjs', 'server.mjs', 'observability.mjs', 'settings.mjs', 'private-state.mjs', 'limits.mjs', 'relay-metrics.mjs', 'build.mjs', 'browser-review.mjs', 'package.json', 'public/style.css', 'public/index.html']
const fingerprints = async names => Promise.all(names.map(async path => ({ path, sha256: createHash('sha256').update(await readFile(new URL(path, import.meta.url))).digest('hex') })))
const sourceFiles = await fingerprints(sourceNames), builtFiles = await fingerprints(['dist/controller.mjs', 'dist/public/client.js', 'dist/public/style.css', 'dist/public/index.html', 'dist/public/nostr-provider.js'])
const sourceRevision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: fileURLToPath(new URL('.', import.meta.url)), encoding: 'utf8' }).trim()
const key = generateSecretKey(), pubkey = getPublicKey(key)
let configured = false, running = false, deleting = false, rooms = 0, devices = 0, pending = 0, setupCalls = 0, loseNextStatus = false, degraded = false, unknown = false, clockOffset = 0
let settingsRevision = 'a'.repeat(64), previousLimits = null
let limits = { maxRooms: 4, aggregateBytesPerSecond: 2000000, maxBytes: 1073741824, minFreeBytes: 2147483648 }
const link = 'https://kithmoot.app/j/#kithmoot-node=component-review-only'
const node = {
  status: async () => dashboardSnapshot({ base: { v: 1, host: 'node.example', configured, running, deleting, limits, paused: !running, settings: { revision: settingsRevision, editable: configured && !running && !deleting, previous: previousLimits } },
    state: running ? { rooms, devices, pending, paired: false, ready: !deleting && !degraded } : undefined,
    doctor: running ? healthReport({ v: 1, version: '0.1.0-rc.1', localReady: !degraded, checks: checkNames.map(name => ({ name, ok: !(degraded && name === 'STUN-TLS-443') })) }, degraded ? 1 : 0, Date.now()) : undefined,
    resources: unknown ? { sampledAt: Date.now() } : { sampledAt: Date.now(), memoryBytes: 103300000, memoryLimitBytes: 268435456, cpuPercent: 1.2, cpuLimitCores: 2, freeBytes: 4000000000 },
    relay: running && !unknown ? { sampledAt: Date.now(), uptimeSeconds: 60, allocations: 3, streamConnections: 2, forwardedBytes: 6000000, bytesPerSecond: 1000000, intervalSeconds: 10, udp: { allocations: 1, forwardedBytes: 1000000, bytesPerSecond: 200000 }, stream: { allocations: 2, forwardedBytes: 5000000, bytesPerSecond: 800000 }, forwardedPackets: 5000, droppedPackets: 2, streamErrors: 0, refusedStreams: 0 } : undefined,
    shelter: running && !unknown ? { responding: true, storeBytes: 65536 } : undefined, certificate: { validUntil: 1800000000000 }, problem: degraded ? 'local-checks-incomplete' : undefined }),
  setup: async value => { configured = running = true; rooms = 2; devices = 5; pending = 1; setupCalls++; limits = pickLimits(value) }, start: async () => { running = true }, stop: async () => { running = false },
  changeSettings: async (value, restore = false) => {
    if (running) throw new Refused(409, 'pause-before-settings')
    if (value.revision !== settingsRevision) throw new Refused(409, 'settings-changed')
    const next = restore ? previousLimits : value.limits
    if (next.maxRooms < rooms) throw new Refused(409, 'settings-room-limit-too-small')
    previousLimits = restore ? null : structuredClone(limits); limits = structuredClone(next)
    settingsRevision = settingsRevision === 'a'.repeat(64) ? 'b'.repeat(64) : 'a'.repeat(64)
    return { saved: true, paused: true, revision: settingsRevision }
  },
  pair: async () => ({ link, expiresAt: Math.floor(Date.now() / 1000) + 360, qr: await QRCode.toString(link, { type: 'svg' }) }),
  prepareDelete: async () => { assert.equal(rooms + devices + pending, 0); deleting = true; return { deleteReady: true } }, cancelDelete: async () => { deleting = false; return { deleteReady: false } }
}
const server = createController({ owners: new Set([pubkey]), hosts: ['node.example'], node, publicDirectory: fileURLToPath(new URL('./dist/public/', import.meta.url)), now: () => Date.now() + clockOffset, monotonic: () => performance.now() + clockOffset })
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const base = 'http://127.0.0.1:' + server.address().port
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined })
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', permissions: ['clipboard-read', 'clipboard-write'] })
const page = await context.newPage(), errors = [], accessibility = [], screenshots = []
page.on('pageerror', error => errors.push(error.message))
await page.exposeFunction('fixtureSign', event => finalizeEvent(event, key))
await context.route('**/*', async route => {
  const input = route.request(), url = new URL(input.url())
  if (url.hostname !== 'node.example') return route.abort()
  if (loseNextStatus && url.pathname === '/api/status') { loseNextStatus = false; return route.abort() }
  if (['/review-host', '/review-host-no-clipboard'].includes(url.pathname)) return route.fulfill({ headers: url.pathname.endsWith('no-clipboard') ? { 'Permissions-Policy': 'clipboard-write=()' } : {}, contentType: 'text/html', body: '<!doctype html><html lang="en"><head><title>Archy embedded component fixture</title></head><body style="margin:0;background:#16181d"><iframe title="KithMoot Node" src="/" style="display:block;border:0;width:100%;height:844px"></iframe></body></html>' })
  if (url.pathname === '/nostr-provider.js') return route.fulfill({ contentType: 'text/javascript', body: `window.archipelagoNostr={selectIdentity:async()=>{},onIdentitySelected:()=>{}};window.nostr={getPublicKey:async()=>${JSON.stringify(pubkey)},signEvent:event=>window.fixtureSign(event)};` })
  const response = await new Promise((resolve, reject) => {
    const req = request(base + url.pathname + url.search, { method: input.method(), headers: { ...input.headers(), host: url.host } }, reply => {
      const chunks = []; reply.on('data', bytes => chunks.push(bytes)); reply.on('end', () => resolve({ status: reply.statusCode, headers: reply.headers, body: Buffer.concat(chunks) })); reply.on('error', reject)
    })
    req.on('error', reject); req.end(input.postDataBuffer())
  })
  await route.fulfill(response)
})
async function capture(name, width = 390, height = 844, enlarged = false) {
  await page.setViewportSize({ width, height })
  await page.evaluate(value => { document.documentElement.style.fontSize = value ? '200%' : '' }, enlarged)
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), name + ': horizontal overflow')
  const path = join(directory, name + '.png')
  await page.screenshot({ path, fullPage: true }); screenshots.push(name + '.png')
}
async function refreshStatus() {
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click()
  await page.locator('#content[aria-busy="false"]').waitFor()
}
async function axe(name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const violations = result.violations.map(item => ({ id: item.id, impact: item.impact, targets: item.nodes.map(node => node.target) }))
  accessibility.push({ name, violations }); assert.deepEqual(violations, [], name + ': accessibility violations')
}
try {
  if (process.env.E2E_KITHMOOT_NODE_CLIPBOARD_ONLY !== '1') {
  await page.goto('https://node.example:3753/')
  await page.getByRole('button', { name: 'Choose identity and sign in' }).waitFor()
  await capture('01-sign-in-390'); await axe('sign-in')
  await page.getByRole('button', { name: 'Choose identity and sign in' }).click()
  await page.getByRole('heading', { name: 'Set up your node' }).waitFor()
  await capture('02-setup-390'); await capture('03-setup-320', 320, 740); await axe('setup')
  await page.getByRole('button', { name: 'Delete everything…' }).click()
  await page.getByRole('button', { name: 'Check rooms and prepare deletion' }).click()
  await page.getByRole('heading', { name: 'Return to Archy to finish' }).waitFor()
  await capture('00-delete-before-setup'); await axe('unconfigured-deletion')
  await page.getByRole('button', { name: 'Cancel deletion' }).click()
  await page.getByRole('heading', { name: 'Set up your node' }).waitFor()
  await page.getByRole('button', { name: 'Set up node', exact: true }).click()
  assert.equal(setupCalls, 0)
  await page.getByRole('checkbox').check(); await page.getByRole('button', { name: 'Set up node', exact: true }).click()
  await page.getByRole('button', { name: 'Pair with KithMoot', exact: true }).waitFor()
  await capture('04-status-390'); await capture('05-status-768', 768, 1024); await capture('06-status-1440', 1440, 900)
  await capture('07-status-large-text', 390, 844, true)
  await page.evaluate(() => { document.documentElement.style.fontSize = '' }); await page.setViewportSize({ width: 390, height: 844 }); await axe('status')
  loseNextStatus = true
  await refreshStatus()
  await page.getByText('Cannot reach the Archy controls.', { exact: false }).waitFor()
  await capture('14-controls-connection-lost-390')
  await refreshStatus()
  assert.equal(await page.locator('#notice').isVisible(), false)
  for (const title of ['Connections', 'Usage', 'Settings', 'Diagnostics']) {
    const nav = page.getByRole('navigation', { name: 'Node views' }).getByRole('button', { name: title, exact: true })
    await nav.focus(); await page.keyboard.press('Enter')
    await page.locator(`[data-page="${title.toLowerCase()}"][aria-current="page"]`).waitFor()
    await axe(title.toLowerCase())
    if (title === 'Settings') assert(await page.getByRole('button', { name: 'Change limits', exact: true }).isDisabled())
    for (const [width, height] of [[320, 740], [390, 844], [768, 1024], [1440, 900], [844, 390]]) await capture(`dashboard-${title.toLowerCase()}-${width}`, width, height)
    await capture(`dashboard-${title.toLowerCase()}-large-text`, 390, 844, true)
    await page.evaluate(() => { document.documentElement.style.fontSize = '' })
  }
  // The same signed controller serves degraded results and paused/unknown data.
  degraded = true
  await refreshStatus()
  await page.getByText('Failed locally', { exact: true }).waitFor()
  await capture('dashboard-diagnostics-failed-443'); await axe('failed-check')
  await page.getByRole('button', { name: 'Copy diagnostics', exact: true }).click()
  await page.getByText('Diagnostics copied. Review the report before sharing it.').waitFor()
  const report = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
  assert.equal(report.connections.external, 'not-measured'); assert.equal(report.devices, 5)
  assert(!JSON.stringify(report).includes('component-review-only')); assert(!report.token); assert(!report.pairing)
  degraded = false; unknown = true
  await page.getByRole('button', { name: 'Usage', exact: true }).click(); await refreshStatus()
  assert(await page.getByText('Unavailable', { exact: true }).count() >= 3)
  await capture('dashboard-usage-unavailable'); unknown = false
  await page.getByRole('button', { name: 'Overview', exact: true }).click()
  await refreshStatus()
  await page.getByRole('button', { name: 'Overview', exact: true }).focus()
  await page.waitForTimeout(11000)
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.page), 'overview', 'background refresh must preserve keyboard focus')
  await page.getByRole('button', { name: 'Pair with KithMoot', exact: true }).click()
  await page.getByRole('heading', { name: 'Pair with your KithMoot app' }).waitFor()
  await page.getByRole('button', { name: 'Copy pairing link', exact: true }).click()
  await page.getByText('Pairing link copied. Keep it private.', { exact: true }).waitFor()
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), link)
  await capture('08-pairing-390'); assert.equal(await page.getByRole('link', { name: 'Open KithMoot' }).getAttribute('href'), link); await axe('pairing')
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('button', { name: 'Pause node' }).click(); await page.getByRole('button', { name: 'Start node' }).waitFor()
  await capture('09-paused-390')
  pending = 0
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByRole('button', { name: 'Change limits', exact: true }).click()
  await page.getByRole('heading', { name: 'Change node limits' }).waitFor()
  await axe('settings-editor')
  for (const [width, height] of [[320,740],[390,844],[768,1024],[1440,900],[844,390]]) await capture('settings-editor-'+width,width,height)
  await capture('settings-editor-large-text',390,844,true); await page.evaluate(()=>{document.documentElement.style.fontSize=''})
  await page.locator('select[name=maxRooms]').selectOption('1')
  await page.getByRole('button', { name: 'Save settings', exact: true }).click()
  await page.getByText('The room limit is lower than', { exact: false }).waitFor()
  assert.equal(await page.locator('select[name=maxRooms]').inputValue(), '1')
  assert(await page.getByRole('button', { name: 'Save settings', exact: true }).isEnabled())
  await capture('settings-editor-room-rejected'); await axe('settings-editor-rejection')
  await page.locator('select[name=maxRooms]').selectOption('8')
  await page.evaluate(()=>window.dispatchEvent(new Event('online')))
  await page.waitForTimeout(11000)
  assert.equal(await page.locator('select[name=maxRooms]').inputValue(), '8', 'reconnect/poll must keep the draft')
  settingsRevision = 'c'.repeat(64)
  await page.getByRole('button', { name: 'Save settings', exact: true }).click()
  await page.getByText('Settings changed in another window.', { exact: false }).waitFor()
  assert.equal(limits.maxRooms,4); await capture('settings-editor-conflict')
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.getByRole('button', { name: 'Change limits', exact: true }).click()
  await page.locator('select[name=maxRooms]').selectOption('8')
  await page.getByRole('button', { name: 'Save settings', exact: true }).click()
  await page.getByText('Settings saved. The node is still paused.', { exact: false }).waitFor()
  assert.equal(running,false);assert.equal(limits.maxRooms,8)
  await page.getByRole('button', { name: 'Restore previous limits', exact: true }).waitFor()
  await capture('settings-saved-paused');await axe('settings-saved-rollback')
  await page.getByRole('button', { name: 'Restore previous limits', exact: true }).click()
  await page.getByText('Previous limits restored.',{exact:false}).waitFor()
  assert.equal(limits.maxRooms,4);assert.equal(running,false)
  await page.getByRole('button', { name: 'Overview', exact: true }).click()
  await page.getByRole('button', { name: 'Start node' }).click()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByRole('button', { name: 'Delete everything…' }).click()
  await capture('10-delete-390'); await axe('delete')
  // Model the owner closing the two rooms in KithMoot before preparation.
  rooms = devices = pending = 0
  await page.getByRole('button', { name: 'Check rooms and prepare deletion' }).click()
  await page.getByRole('button', { name: 'Cancel deletion' }).waitFor(); await capture('11-delete-prepared-390')
  await page.getByRole('button', { name: 'Cancel deletion' }).click()
  await page.getByRole('button', { name: 'Overview', exact: true }).click()
  await page.getByRole('button', { name: 'Pair with KithMoot', exact: true }).waitFor()
  await capture('13-landscape', 844, 390)
  await page.evaluate(() => document.documentElement.classList.add('no-blur'))
  await capture('dashboard-diagnostics-no-blur'); await axe('standalone-no-blur')
  await page.evaluate(() => document.documentElement.classList.remove('no-blur'))
  clockOffset = 31 * 60000
  await refreshStatus()
  await page.getByRole('button', { name: 'Choose identity and sign in' }).waitFor()
  await capture('dashboard-session-expired'); assert.equal(running, true, 'controls expiry does not stop node')
  clockOffset = 0
  await page.getByRole('button', { name: 'Choose identity and sign in' }).click()
  await page.getByRole('button', { name: 'Sign out' }).click()
  // An actual same-origin iframe on the documented dark host canvas. The
  // host gate/signer remain fixtures; contrast is checked after composition.
  const embeddedPage = await context.newPage()
  embeddedPage.on('pageerror', error => errors.push(error.message))
  await embeddedPage.exposeFunction('fixtureSign', event => finalizeEvent(event, key))
  await embeddedPage.goto('https://node.example:3753/review-host')
  const embedded = embeddedPage.frameLocator('iframe')
  await embedded.getByRole('button', { name: 'Choose identity and sign in' }).click()
  await embedded.getByRole('button', { name: 'Overview', exact: true }).waitFor()
  for (const title of ['Overview', 'Connections', 'Usage', 'Settings', 'Diagnostics']) {
    await embeddedPage.locator('iframe').evaluate(element => { element.style.height = '844px' })
    await embedded.getByRole('button', { name: title, exact: true }).click()
    const frame = embeddedPage.frames().find(frame => frame.parentFrame())
    assert(await frame.evaluate(() => document.documentElement.classList.contains('embedded')))
    assert(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    if (title === 'Diagnostics') await frame.evaluate(() => document.documentElement.classList.add('no-blur'))
    const height = await frame.evaluate(() => document.documentElement.scrollHeight)
    await embeddedPage.locator('iframe').evaluate((element, height) => { element.style.height = height + 'px' }, height)
    const name = `dashboard-${title.toLowerCase()}-embedded-390.png`
    await embeddedPage.screenshot({ path: join(directory, name), fullPage: true }); screenshots.push(name)
    const result = await new AxeBuilder({ page: embeddedPage }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    const violations = result.violations.map(item => ({ id: item.id, impact: item.impact, targets: item.nodes.map(node => node.target) }))
    accessibility.push({ name: 'embedded-' + title.toLowerCase(), violations }); assert.deepEqual(violations, [])
  }
  await embeddedPage.close()
  }
  configured = running = true; rooms = 1; devices = 3; pending = 0
  // Reproduce the actual host-policy refusal rather than mocking writeText.
  const blockedPage = await context.newPage()
  blockedPage.setDefaultTimeout(10000)
  blockedPage.on('pageerror', error => errors.push(error.message))
  await blockedPage.exposeFunction('fixtureSign', event => finalizeEvent(event, key))
  await blockedPage.clock.install()
  await blockedPage.goto('https://node.example:3753/review-host-no-clipboard')
  const blocked = blockedPage.frameLocator('iframe')
  await blocked.getByRole('button', { name: 'Choose identity and sign in' }).click()
  await blocked.getByRole('button', { name: 'Pair with KithMoot', exact: true }).click()
  const blockedFrame = blockedPage.frames().find(frame => frame.parentFrame())
  assert.equal(await blockedFrame.evaluate(() => document.featurePolicy.allowsFeature('clipboard-write')), false)
  await blocked.getByRole('button', { name: 'Copy pairing link', exact: true }).click()
  await blocked.getByText('Automatic copying is unavailable. The pairing link is selected; copy it with your keyboard or touch menu.').waitFor()
  const privateLink = blocked.getByLabel('Private pairing link', { exact: true })
  assert.equal(await privateLink.inputValue(), link)
  assert.deepEqual(await privateLink.evaluate(input => ({ readonly: input.readOnly, selected: document.activeElement === input && input.selectionStart === 0 && input.selectionEnd === input.value.length })), { readonly: true, selected: true })
  for (const [width, height, enlarged = false] of [[320,740],[390,844],[768,1024],[1440,900],[844,390],[390,844,true]]) {
    await blockedPage.setViewportSize({ width, height })
    await blockedFrame.evaluate(value => { document.documentElement.style.fontSize = value ? '200%' : '' }, enlarged)
    assert(await blockedFrame.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    await blockedPage.locator('iframe').evaluate(element => { element.style.height = '844px' })
    const frameHeight = await blockedFrame.evaluate(() => document.documentElement.scrollHeight)
    await blockedPage.locator('iframe').evaluate((element, value) => { element.style.height = value + 'px' }, frameHeight)
    await blockedFrame.evaluate(() => scrollTo(0, 0))
    const name = `pairing-copy-blocked-${enlarged ? 'large-text' : width}.png`
    await blockedPage.screenshot({ path: join(directory, name), fullPage: true }); screenshots.push(name)
  }
  await blockedFrame.evaluate(() => { document.documentElement.style.fontSize = '' })
  const blockedAxe = await new AxeBuilder({ page: blockedPage }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const blockedViolations = blockedAxe.violations.map(item => ({ id: item.id, impact: item.impact, targets: item.nodes.map(node => node.target) }))
  accessibility.push({ name: 'pairing-clipboard-policy-blocked', violations: blockedViolations }); assert.deepEqual(blockedViolations, [])
  // A browser without the Clipboard API gets the same manual path.
  await blockedFrame.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined }))
  await blocked.getByRole('button', { name: 'Copy pairing link', exact: true }).click()
  assert.equal(await privateLink.inputValue(), link)
  assert(await privateLink.evaluate(input => document.activeElement === input && input.selectionEnd === input.value.length))
  // A clipboard completion arriving after expiry must not revive the link or claim success.
  await blockedFrame.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => new Promise(resolve => { window.finishPairCopy = resolve }) } }))
  await blocked.getByRole('button', { name: 'Copy pairing link', exact: true }).click()
  await blockedFrame.waitForFunction(() => typeof window.finishPairCopy === 'function')
  await blockedPage.clock.fastForward(360001)
  await blocked.getByText('That pairing code expired. Create a fresh code to continue.').waitFor()
  await blockedFrame.evaluate(() => window.finishPairCopy())
  await blocked.locator('#content[aria-busy="false"]').waitFor()
  assert.equal(await blocked.getByText('Pairing link copied. Keep it private.', { exact: true }).count(), 0)
  assert.equal(await privateLink.count(), 0)
  assert.equal(await blocked.getByRole('link', { name: 'Open KithMoot', exact: true }).count(), 0)
  await blockedPage.close()
  assert.deepEqual(errors, [])
  assert.deepEqual(await fingerprints(sourceNames), sourceFiles, 'Source changed during the browser check')
  await writeFile(join(directory, 'component-review.json'), JSON.stringify({ schema: 'kithmoot-node-ui-component/1', passed: true, actualController: true,
    sourceRevision, sourceFiles, builtFiles, fixtureSigner: true, fixtureNodeAdapter: true, embeddedHostFixture: true, actualHostGate: false, actualTurn: false, uiMaintainerApproval: false, zat: 'pending', screenshots, accessibility, pageErrors: errors }, null, 2) + '\n')
  // This guarded fixture owns its dated output directory. Drop obsolete
  // captures from earlier failed runs, never unrelated files or directories.
  if (!process.env.E2E_KITHMOOT_NODE_REVIEW_OUTPUT) for (const name of await readdir(directory)) {
    if (/^[a-z0-9-]+\.png$/.test(name) && !screenshots.includes(name)) await unlink(join(directory, name))
  }
  console.log(`Browser component journey passed; ${screenshots.length} captures, ${accessibility.length} accessibility scans; official Archy ZAT pending.`)
} finally {
  await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); key.fill(0)
}
