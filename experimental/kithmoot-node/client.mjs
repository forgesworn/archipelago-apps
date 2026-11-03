import { sha256 } from '@noble/hashes/sha2.js'
import { bytesToHex } from '@noble/hashes/utils.js'

const content = document.querySelector('#content'), notice = document.querySelector('#notice')
const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char])
let token, status, busy = false, view = 'status', pairing, expiryTimer, polling = false
if (window.parent !== window) document.documentElement.classList.add('embedded')
const messages = {
  'host-identity-required': 'Choose an identity belonging to this Archy node.',
  'sign-in-required': 'Your session ended. Sign in again to continue.',
  'invalid-proof': 'The sign-in proof expired or did not match this node. Please sign in again.',
  'close-rooms-first': 'Close every hosted room in KithMoot first. Wait for the node to confirm that its rooms, devices and pending requests are empty.',
  'node-not-ready': 'The node is not ready to pair. Check its status and try again.',
  'configuration-review-required': 'The saved hostname or address changed. Keep the saved data and review the host configuration before restarting.',
  'setup-incomplete': 'Setup did not finish. Retry the saved setup to continue safely.',
  'retry-saved-setup': 'Retry with the saved setup choices.',
  'node-unavailable': 'The node could not complete that request. Check its status and try again.',
  'busy': 'The node is busy. Wait a moment and try again.'
}
function inform(message, error = false) { notice.textContent = message; notice.hidden = !message; notice.classList.toggle('error', error) }
function clearPairing() { pairing = undefined; clearTimeout(expiryTimer) }
async function api(action, value = {}) {
  const response = await fetch('/api/' + action, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
    body: JSON.stringify(value), credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(65000) })
  const reply = await response.json()
  if (!response.ok) {
    if (response.status === 401) { token = undefined; clearPairing(); renderSignIn() }
    throw Error(messages[reply.error] ?? 'The request could not finish. Try again.')
  }
  return reply.result
}
function mount(html) { content.innerHTML = html; content.setAttribute('aria-busy', 'false'); content.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => run(button.dataset.action))) }
function renderSignIn() {
  mount('<h2>Sign in to manage your node</h2><p>Use an identity belonging to this Archy node. Pairing with KithMoot is a separate step.</p><div class="actions"><button class="primary" data-action="sign-in">Choose identity and sign in</button></div>')
}
async function signIn() {
  if (location.protocol !== 'https:') throw Error('Open this screen through Archy’s HTTPS address to manage the node.')
  if (!window.nostr || !window.archipelagoNostr) throw Error('The Archy signer is unavailable. Open this app from your Archy dashboard and try again.')
  await window.archipelagoNostr.selectIdentity()
  await window.nostr.getPublicKey()
  const challengeResponse = await fetch('/api/challenge', { credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10000) })
  if (!challengeResponse.ok) throw Error('The node could not begin sign-in. Try again.')
  const challenge = await challengeResponse.json(), body = '{}'
  if (challenge.v !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(challenge.nonce)) throw Error('The node returned an invalid sign-in challenge.')
  const event = await window.nostr.signEvent({ kind: 27235, created_at: Math.floor(Date.now() / 1000), content: '',
    tags: [['u', location.origin + '/api/session'], ['method', 'POST'], ['payload', bytesToHex(sha256(new TextEncoder().encode(body)))], ['nonce', challenge.nonce]] })
  const response = await fetch('/api/session', { method: 'POST', body, headers: { 'Content-Type': 'application/json', Authorization: 'Nostr ' + btoa(JSON.stringify(event)) },
    credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10000) })
  const result = await response.json()
  if (!response.ok || !/^[A-Za-z0-9_-]{43}$/.test(result.token ?? '')) throw Error(messages[result.error] ?? 'Sign-in failed. Try again.')
  token = result.token
  view = 'status'; await refresh()
}
function renderSetup() {
  const saved = status.setupPending ? status.limits : undefined
  const select = (name, title, options, initial) => `<label>${title}<select name="${name}" ${saved ? 'disabled' : ''}>${options.map(([value, label]) => `<option value="${value}" ${value === (saved?.[name] ?? initial) ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`
  mount(`<h2>${saved ? 'Finish setting up' : 'Set up your node'}</h2><p>Use a rented server or an Archy hosted away from home. Room calls use this node by default. Files are unavailable in node rooms.</p>
    <form id="setup">
    ${select('maxRooms', 'Hosted rooms', [[1, '1 room'], [4, 'Up to 4 rooms'], [8, 'Up to 8 rooms']], 4)}
    ${select('aggregateBytesPerSecond', 'Total call bandwidth', [[1000000, '8 Mbit/s'], [2000000, '16 Mbit/s'], [5000000, '40 Mbit/s']], 2000000)}
    ${select('maxBytes', 'Message storage limit', [[268435456, '256 MiB'], [1073741824, '1 GiB'], [4294967296, '4 GiB']], 1073741824)}
    ${select('minFreeBytes', 'Leave free on this host', [[1073741824, 'At least 1 GiB'], [2147483648, 'At least 2 GiB']], 2147483648)}
    <label class="check"><input name="away" type="checkbox" required><span>This node is hosted away from my home connection.</span></label>
    <div class="actions"><button class="primary" type="submit">${saved ? 'Retry saved setup' : 'Set up node'}</button><button type="button" data-action="sign-out">Sign out</button></div></form>`)
  content.querySelector('form').addEventListener('submit', event => { event.preventDefault(); void run('setup') })
}
function renderStatus() {
  if (!status.configured) return renderSetup()
  const label = status.deleting ? 'Prepared for deletion' : status.ready ? 'Ready' : status.running ? 'Needs attention' : 'Paused'
  mount(`<span class="badge ${status.ready ? 'ready' : ''}">${label}</span><h2 class="host">${escape(status.host)}</h2>
    <p>${status.deleting ? 'New rooms and requests are blocked. Return to Archy to delete the app and its data, or cancel below.' : status.ready ? 'Your rooms and calls can use this node.' : status.running ? 'The node is running, but its local checks have not passed. Refresh its status before pairing.' : 'Start the node to make hosted rooms and calls available again.'}</p>
    <div class="facts"><div class="fact"><strong>${status.rooms ?? '—'}</strong><span>Hosted rooms</span></div><div class="fact"><strong>${status.devices ?? '—'}</strong><span>Admitted devices</span></div><div class="fact"><strong>${status.pending ?? '—'}</strong><span>Pending requests</span></div><div class="fact"><strong>${status.paired ? 'Paired' : 'Unpaired'}</strong><span>Keeper’s KithMoot app</span></div></div>
    <div class="actions">${status.deleting ? '<button class="primary" data-action="cancel-delete">Cancel deletion</button>' : status.running ? `<button class="primary" data-action="pair" ${status.ready ? '' : 'disabled'}>${status.paired ? 'Pair another keeper device' : 'Pair with KithMoot'}</button><button data-action="pause">Pause node</button>` : '<button class="primary" data-action="start">Start node</button>'}<button data-action="refresh">Refresh status</button></div>
    <hr><p class="muted">Kicking someone and closing a room happen in KithMoot. Pausing this node keeps its saved data.</p><div class="actions"><button class="danger" data-action="delete" ${status.running && !status.deleting ? '' : 'disabled'}>Delete everything…</button><button data-action="sign-out">Sign out</button></div>`)
}
function renderDelete() {
  mount('<h2>Delete this node and its data</h2><p>First close every hosted room in KithMoot. Closing revokes access, ends calls, purges the room’s messages and sends the devices their self-destruct instruction.</p><p>Prepare deletion below once all rooms, devices and pending requests are gone. Then use Archy’s <strong>Delete app and data</strong> action. This screen cannot close rooms for you.</p><div class="actions"><button class="danger" data-action="prepare-delete">Check rooms and prepare deletion</button><button data-action="back">Keep node</button></div>')
}
function renderPairing() {
  mount('<h2>Pair with your KithMoot app</h2><p>Scan this code with your keeper device, or open the link on this device. Anyone holding this code can attempt keeper pairing. Keep it private.</p><div class="qr"><img alt="Private KithMoot keeper pairing code" width="256" height="256"></div><p>This code expires within six minutes. Guests join through a room link after you admit them.</p><a class="button primary" id="open-pair">Open KithMoot</a><div class="actions"><button data-action="copy-pair">Copy pairing link</button><button data-action="back">Done</button></div>')
  content.querySelector('img').src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(pairing.qr)
  content.querySelector('#open-pair').href = pairing.link
}
async function refresh() { status = await api('status'); if (view === 'status') renderStatus() }
async function run(action) {
  if (busy) return
  busy = true; inform(''); content.setAttribute('aria-busy', 'true')
  content.querySelectorAll('button').forEach(button => { button.disabled = true })
  try {
    if (action === 'sign-in') await signIn()
    else if (action === 'sign-out') { token = undefined; clearPairing(); renderSignIn() }
    else if (action === 'delete') { view = 'delete'; renderDelete() }
    else if (action === 'back') { clearPairing(); view = 'status'; await refresh() }
    else if (action === 'copy-pair') { await navigator.clipboard.writeText(pairing.link); inform('Pairing link copied. Keep it private.') }
    else if (action === 'pair') {
      pairing = await api('pair'); view = 'pair'; renderPairing()
      clearTimeout(expiryTimer)
      expiryTimer = setTimeout(() => { clearPairing(); view = 'status'; renderStatus(); inform('That pairing code expired. Create a fresh code to continue.') }, Math.max(0, Math.min(360000, pairing.expiresAt * 1000 - Date.now())))
    } else if (action === 'setup') {
      const form = content.querySelector('form'), value = { hostedAwayFromHome: form.elements.away.checked }
      for (const key of ['maxRooms', 'aggregateBytesPerSecond', 'maxBytes', 'minFreeBytes']) value[key] = Number(form.elements[key].value)
      await api('setup', value); view = 'status'; await refresh(); inform('Node setup saved.')
    } else {
      if (action !== 'refresh') await api(action)
      view = 'status'; await refresh()
      if (action === 'prepare-delete') inform('Prepared for deletion. Return to Archy and choose Delete app and data.')
    }
  } catch (error) { inform(error instanceof Error && error.name !== 'TypeError' ? error.message : 'The node is unreachable. Check your connection and try again.', true) }
  finally {
    busy = false; content.setAttribute('aria-busy', 'false')
    // Re-rendering restores only the controls appropriate to the current state.
    if (token && view === 'status' && status) renderStatus()
    else if (token && view === 'delete') renderDelete()
    else if (token && view === 'pair' && pairing) renderPairing()
    else if (!token) renderSignIn()
  }
}
window.addEventListener('online', () => { if (token && !busy) void run('refresh') })
window.addEventListener('offline', () => inform('You are offline. Reconnect to manage the node.', true))
window.archipelagoNostr?.onIdentitySelected(() => { token = undefined; clearPairing(); if (!busy) renderSignIn() })
setInterval(async () => {
  if (!token || busy || polling || view !== 'status' || !status?.configured || document.hidden) return
  polling = true
  try { await refresh() } catch (error) { inform(error.message, true) } finally { polling = false }
}, 10000)
renderSignIn()
