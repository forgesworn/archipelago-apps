import { sha256 } from '@noble/hashes/sha2.js'
import { bytesToHex } from '@noble/hashes/utils.js'
import { dashboard, supportReport, escape, limitFields, settingsEditor } from './dashboard.mjs'

const content = document.querySelector('#content'), notice = document.querySelector('#notice')
let token, status, busy = false, view = 'status', pairing, expiryTimer, polling = false
let activityPending = false, dashboardPage = 'overview', returnAction, editingSettings
if (window.parent !== window) document.documentElement.classList.add('embedded')
const messages = {
  'host-identity-required': 'Choose an identity belonging to this Archy node.',
  'sign-in-required': 'Your controls session ended. Sign in again to manage the node. Rooms and calls are unaffected.',
  'invalid-proof': 'The sign-in proof expired or did not match this node. Please sign in again.',
  'close-rooms-first': 'Close every hosted room in KithMoot first. Wait for the node to confirm that its rooms, devices and pending requests are empty.',
  'node-not-ready': 'The node is not ready to pair. Check its status and try again.',
  'configuration-review-required': 'The saved hostname or address changed. Keep the saved data and review the host configuration before restarting.',
  'setup-incomplete': 'Setup did not finish. Retry the saved setup to continue safely.',
  'retry-saved-setup': 'Retry with the saved setup choices.',
  'deletion-prepared': 'Deletion is prepared. Cancel deletion before setting up or starting the node.',
  'node-unavailable': 'The node could not complete that request. Check its status and try again.',
  'pause-before-settings': 'Pause the node from Overview before changing limits. Saving keeps it paused.',
  'settings-changed': 'Settings changed in another window. Cancel and refresh before trying again.',
  'settings-room-limit-too-small': 'The room limit is lower than the number of saved rooms. Keep a larger limit or close rooms in KithMoot first.',
  'settings-storage-limit-too-small': 'The storage limit is lower than the saved message files. Keep a larger limit; no messages were removed.',
  'settings-disk-reserve-unavailable': 'The host has less free space than this reserve. Free space on the host or choose a smaller reserve.',
  'settings-operations-pending': 'A room change is unfinished. Start the node and let it finish before pausing and changing limits.',
  'settings-usage-unavailable': 'Saved usage could not be checked safely. Settings have not been changed.',
  'settings-review-required': 'Saved settings need a configuration review. Keep the existing data.',
  'invalid-settings': 'Choose one of the available limits and try again.',
  'no-previous-settings': 'There are no previous limits to restore.',
  'node-pause-failed': 'The node did not confirm that it stopped. Refresh its status before trying again.',
  'busy': 'The node is busy. Wait a moment and try again.'
}
function inform(message, error = false) { notice.textContent = message; notice.hidden = !message; notice.classList.toggle('error', error) }
const managementConnectionError = 'Cannot reach the Archy controls. Check your private connection to Archy, then refresh these controls.'
function errorMessage(error) { return error instanceof Error && !['TypeError', 'TimeoutError', 'AbortError'].includes(error.name) ? error.message : managementConnectionError }
function clearPairing() { pairing = undefined; clearTimeout(expiryTimer) }
async function api(action, value = {}, activity = true) {
  const response = await fetch('/api/' + action, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token, ...(activity ? { 'X-Kithmoot-Activity': 'user' } : {}) },
    body: JSON.stringify(value), credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(65000) })
  const reply = await response.json()
  if (!response.ok) {
    if (response.status === 401) { token = undefined; clearPairing(); renderSignIn() }
    throw Error(messages[reply.error] ?? 'The request could not finish. Try again.')
  }
  if (activity) activityPending = false
  return reply.result
}
function mount(html) {
  const active = content.contains(document.activeElement) ? document.activeElement : null
  const focus = active?.dataset.page ? `[data-page="${active.dataset.page}"]` : active?.dataset.action ? `[data-action="${active.dataset.action}"]` : null
  content.innerHTML = html; content.setAttribute('aria-busy', 'false')
  content.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => run(button.dataset.action)))
  content.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => { if (!busy) { dashboardPage = button.dataset.page; renderStatus() } }))
  if (focus) content.querySelector(focus)?.focus({ preventScroll: true })
}
function renderSignIn() {
  mount('<h2>Sign in to manage your node</h2><p>Use an identity belonging to this Archy node. Pairing with KithMoot is a separate step.</p><p class="muted">These controls sign out after 30 minutes without use, or after eight hours. This does not stop your rooms or calls.</p><div class="actions"><button class="primary" data-action="sign-in">Choose identity and sign in</button></div>')
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
  token = result.token; dashboardPage = 'overview'
  view = 'status'; await refresh()
}
function renderSetup() {
  const saved = status.setupPending ? status.limits : undefined
  mount(`<h2>${saved ? 'Finish setting up' : 'Set up your node'}</h2><p>Use a rented server or an Archy hosted away from home. Room calls use this node by default. Files are unavailable in node rooms.</p>
    <form id="setup">
    ${limitFields(saved, !!saved)}
    <label class="check"><input name="away" type="checkbox" required><span>This node is hosted away from my home connection.</span></label>
    <div class="actions"><button class="primary" type="submit">${saved ? 'Retry saved setup' : 'Set up node'}</button><button type="button" data-action="sign-out">Sign out</button><button type="button" class="danger" data-action="delete">Delete everything…</button></div></form>`)
  content.querySelector('form').addEventListener('submit', event => { event.preventDefault(); void run('setup') })
}
function renderStatus() {
  if (!status.configured && status.deleting) return mount('<span class="badge">Prepared for deletion</span><h2>Return to Archy to finish</h2><p>Setup is blocked. Use Archy’s <strong>Delete app and data</strong> action, or cancel deletion below to return to setup.</p><div class="actions"><button class="primary" data-action="cancel-delete">Cancel deletion</button><button data-action="sign-out">Sign out</button></div>')
  if (!status.configured) return renderSetup()
  mount(dashboard(status, dashboardPage))
}
function renderSettingsEditor(draft) {
  mount(settingsEditor(status, draft))
  content.querySelector('form').addEventListener('submit', event => { event.preventDefault(); void run('save-settings') })
}
function renderDelete() {
  mount('<h2>Delete this node and its data</h2><p>First close every hosted room in KithMoot. Closing revokes access, ends calls, purges the room’s messages and sends the devices their self-destruct instruction.</p><p>Prepare deletion below once all rooms, devices and pending requests are gone. Then use Archy’s <strong>Delete app and data</strong> action. This screen cannot close rooms for you.</p><div class="actions"><button class="danger" data-action="prepare-delete">Check rooms and prepare deletion</button><button data-action="back">Keep node</button></div>')
}
function renderPairing() {
  mount('<h2>Pair with your KithMoot app</h2><p>Open this link in KithMoot on the browser, computer or phone you want to use. Sign in to the same KithMoot account on each device. This code connects that account to your node. Keep it private.</p><div class="qr"><img alt="Private KithMoot pairing code" width="256" height="256"></div><p>This code expires within six minutes. Guests join through a room link after you admit them.</p><a class="button primary" id="open-pair">Open KithMoot</a><label for="pairing-link" class="pair-link">Private pairing link</label><input id="pairing-link" class="copy-link" type="text" readonly autocomplete="off" autocapitalize="off" spellcheck="false"><div class="actions"><button data-action="copy-pair">Copy pairing link</button><button data-action="back">Done</button></div>')
  content.querySelector('img').src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(pairing.qr)
  content.querySelector('#open-pair').href = pairing.link
  content.querySelector('#pairing-link').value = pairing.link
}
async function refresh(activity = true) { status = await api('status', {}, activity); if (view === 'status') renderStatus() }
async function run(action, activity = true) {
  if (busy) return
  let settingsDraft, manualPairing
  if (view === 'settings-edit') settingsDraft = Object.fromEntries(['maxRooms', 'aggregateBytesPerSecond', 'maxBytes', 'minFreeBytes'].map(name => [name, Number(content.querySelector('form').elements[name].value)]))
  const focusAction = action === 'back' ? returnAction : ['save-settings', 'restore-settings'].includes(action) ? 'edit-settings' : action === 'sign-out' ? 'sign-in' : action
  busy = true; inform(''); content.setAttribute('aria-busy', 'true')
  content.querySelectorAll('button').forEach(button => { button.disabled = true })
  try {
    if (action === 'sign-in') await signIn()
    else if (action === 'sign-out') { try { await api('sign-out') } finally { token = undefined; clearPairing(); renderSignIn() } }
    else if (action === 'edit-settings') { editingSettings = status.settings; returnAction = 'edit-settings'; view = 'settings-edit'; renderSettingsEditor() }
    else if (action === 'save-settings') {
      await api('settings', { revision: editingSettings.revision, limits: settingsDraft }); view = 'status'; dashboardPage = 'settings'; await refresh(); inform('Settings saved. The node is still paused. Start it from Overview when ready.')
    }
    else if (action === 'restore-settings') {
      await api('restore-settings', { revision: status.settings.revision }); await refresh(); inform('Previous limits restored. The node is still paused.')
    }
    else if (action === 'delete') { returnAction = 'delete'; view = 'delete'; renderDelete() }
    else if (action === 'back') { clearPairing(); view = 'status'; await refresh() }
    else if (action === 'copy-diagnostics') { await navigator.clipboard.writeText(supportReport(status)); inform('Diagnostics copied. Review the report before sharing it.') }
    else if (action === 'copy-pair') {
      const current = pairing
      try {
        await navigator.clipboard.writeText(current.link)
        if (pairing === current && view === 'pair' && token) inform('Pairing link copied. Keep it private.')
      } catch {
        if (pairing === current && view === 'pair' && token) {
          manualPairing = current
          inform('Automatic copying is unavailable. The pairing link is selected; copy it with your keyboard or touch menu.')
        }
      }
    }
    else if (action === 'pair') {
      returnAction = 'pair'
      pairing = await api('pair'); view = 'pair'; renderPairing()
      clearTimeout(expiryTimer)
      expiryTimer = setTimeout(() => { clearPairing(); view = 'status'; renderStatus(); inform('That pairing code expired. Create a fresh code to continue.') }, Math.max(0, Math.min(360000, pairing.expiresAt * 1000 - Date.now())))
    } else if (action === 'setup') {
      const form = content.querySelector('form'), value = { hostedAwayFromHome: form.elements.away.checked }
      for (const key of ['maxRooms', 'aggregateBytesPerSecond', 'maxBytes', 'minFreeBytes']) value[key] = Number(form.elements[key].value)
      await api('setup', value); view = 'status'; await refresh(); inform('Node setup saved.')
    } else {
      if (action !== 'refresh') await api(action)
      if (['prepare-delete', 'cancel-delete'].includes(action)) dashboardPage = 'overview'
      view = 'status'; await refresh(activity)
      if (action === 'prepare-delete') inform('Prepared for deletion. Return to Archy and choose Delete app and data.')
    }
  } catch (error) { inform(errorMessage(error), true) }
  finally {
    busy = false; content.setAttribute('aria-busy', 'false')
    // Re-rendering restores only the controls appropriate to the current state.
    if (token && view === 'status' && status) renderStatus()
    else if (token && view === 'delete') renderDelete()
    else if (token && view === 'pair' && pairing) renderPairing()
    else if (token && view === 'settings-edit') renderSettingsEditor(settingsDraft)
    else if (!token) renderSignIn()
    const target = content.querySelector(`[data-action="${focusAction}"]:not(:disabled)`)
    if (manualPairing && manualPairing === pairing && view === 'pair') {
      const input = content.querySelector('#pairing-link')
      input.focus({ preventScroll: true }); input.select()
    }
    else if (target) target.focus({ preventScroll: true })
    else if (['pair', 'delete', 'prepare-delete', 'cancel-delete', 'edit-settings'].includes(action)) { const heading = content.querySelector('h2'); if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }) } }
  }
}
for (const name of ['pointerdown', 'keydown']) document.addEventListener(name, event => { if (event.isTrusted) activityPending = true }, { passive: true })
window.addEventListener('online', () => { if (token && !busy && view === 'status') void run('refresh', false); else if (token) inform('Your browser is online again. Your current screen is still open.') })
window.addEventListener('offline', () => inform('You are offline. Reconnect to manage the node.', true))
window.archipelagoNostr?.onIdentitySelected(() => { token = undefined; clearPairing(); if (!busy) renderSignIn() })
setInterval(async () => {
  if (!token || busy || polling || view !== 'status' || !status?.configured || document.hidden) return
  polling = true
  try { await refresh(activityPending); if (notice.textContent === managementConnectionError) inform('Connection to the Archy controls restored.') }
  catch (error) { inform(errorMessage(error), true) } finally { polling = false }
}, 10000)
renderSignIn()
