// Component review only. API signatures use the real controller; the node
// adapter and Archy signer are fixtures. Host/TURN integration is separate.
import assert from 'node:assert/strict'
import { request } from 'node:http'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../tests/smoke/node_modules/playwright-core/index.mjs'
import AxeBuilder from '../../tests/smoke/node_modules/@axe-core/playwright/dist/index.mjs'
import { generateSecretKey, getPublicKey, finalizeEvent } from 'nostr-tools/pure'
import QRCode from 'qrcode'
import { createController } from './server.mjs'

assert.equal(process.env.E2E_KITHMOOT_NODE_UI, 'component-review')
const directory = fileURLToPath(new URL('../../docs/evidence/kithmoot-node-archy-20261103/', import.meta.url))
await mkdir(directory, { recursive: true })
const key = generateSecretKey(), pubkey = getPublicKey(key)
let configured = false, running = false, deleting = false, rooms = 0, setupCalls = 0
const link = 'https://kithmoot.app/j/#kithmoot-node=component-review-only'
const node = {
  status: async () => ({ v: 1, host: 'node.example', configured, running, ready: running && !deleting, paired: false, rooms, devices: 0, pending: 0, deleting }),
  setup: async () => { configured = running = true; setupCalls++ }, start: async () => { running = true }, stop: async () => { running = false },
  pair: async () => ({ link, expiresAt: Math.floor(Date.now() / 1000) + 360, qr: await QRCode.toString(link, { type: 'svg' }) }),
  prepareDelete: async () => { deleting = true; return { deleteReady: true } }, cancelDelete: async () => { deleting = false; return { deleteReady: false } }
}
const server = createController({ owners: new Set([pubkey]), hosts: ['node.example'], node, publicDirectory: fileURLToPath(new URL('./dist/public/', import.meta.url)) })
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const base = 'http://127.0.0.1:' + server.address().port
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined })
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
const page = await context.newPage(), errors = [], accessibility = [], screenshots = []
page.on('pageerror', error => errors.push(error.message))
await page.exposeFunction('fixtureSign', event => finalizeEvent(event, key))
await context.route('**/*', async route => {
  const input = route.request(), url = new URL(input.url())
  if (url.hostname !== 'node.example') return route.abort()
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
async function axe(name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const violations = result.violations.map(item => ({ id: item.id, impact: item.impact, targets: item.nodes.map(node => node.target) }))
  accessibility.push({ name, violations }); assert.deepEqual(violations, [], name + ': accessibility violations')
}
try {
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
  await page.getByRole('button', { name: 'Pair with KithMoot', exact: true }).click()
  await page.getByRole('heading', { name: 'Pair with your KithMoot app' }).waitFor()
  await capture('08-pairing-390'); assert.equal(await page.getByRole('link', { name: 'Open KithMoot' }).getAttribute('href'), link); await axe('pairing')
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('button', { name: 'Pause node' }).click(); await page.getByRole('button', { name: 'Start node' }).waitFor()
  await capture('09-paused-390'); await page.getByRole('button', { name: 'Start node' }).click()
  await page.getByRole('button', { name: 'Delete everything…' }).click()
  await capture('10-delete-390'); await axe('delete')
  await page.getByRole('button', { name: 'Check rooms and prepare deletion' }).click()
  await page.getByRole('button', { name: 'Cancel deletion' }).waitFor(); await capture('11-delete-prepared-390')
  await page.getByRole('button', { name: 'Cancel deletion' }).click()
  await page.getByRole('button', { name: 'Pair with KithMoot', exact: true }).waitFor()
  await page.evaluate(() => document.documentElement.classList.add('embedded'))
  await capture('12-embedded-390'); await capture('13-landscape', 844, 390)
  await page.getByRole('button', { name: 'Sign out' }).click()
  assert.deepEqual(errors, [])
  await writeFile(join(directory, 'component-review.json'), JSON.stringify({ schema: 'kithmoot-node-ui-component/1', passed: true, actualController: true,
    fixtureSigner: true, fixtureNodeAdapter: true, actualHostGate: false, actualTurn: false, uiMaintainerApproval: false, zat: 'pending', screenshots, accessibility, pageErrors: errors }, null, 2) + '\n')
  console.log('Browser component journey passed; 14 captures, six accessibility scans, ZAT pending.')
} finally {
  await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); key.fill(0)
}
