export const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char])
const known = value => typeof value === 'number' && Number.isFinite(value) && value >= 0
const count = value => known(value) ? escape(value.toLocaleString()) : 'Unavailable'
const bytes = value => {
  if (!known(value)) return 'Unavailable'
  const scale = value >= 1073741824 ? [1073741824, 'GiB'] : value >= 1048576 ? [1048576, 'MiB'] : value >= 1024 ? [1024, 'KiB'] : [1, 'B']
  return (value / scale[0]).toLocaleString(undefined, { maximumFractionDigits: 1 }) + ' ' + scale[1]
}
const date = value => known(value) && value > 0 ? escape(new Date(value).toLocaleString()) : 'Not checked'
const uptime = value => !known(value) ? 'Unavailable' : value >= 3600 ? `${Math.floor(value / 3600)}h ${Math.floor(value % 3600 / 60)}m` : `${Math.floor(value / 60)}m ${Math.floor(value % 60)}s`
const fact = (title, value, detail = '') => `<div class="fact"><dt>${title}</dt><dd>${value}</dd>${detail ? `<dd class="muted fact-detail">${detail}</dd>` : ''}</div>`
const row = (title, value, detail = '') => `<div class="detail-row"><dt>${title}</dt><dd>${value}${detail ? `<span class="muted row-detail">${detail}</span>` : ''}</dd></div>`
const stateLabels = { passed: 'Passed locally', failed: 'Failed locally', unknown: 'Not confirmed', stopped: 'Stopped', responding: 'Responding', attention: 'Needs attention' }
const badge = state => `<span class="badge ${['passed', 'responding'].includes(state) ? 'ready' : ''}">${escape(stateLabels[state] ?? 'Not confirmed')}</span>`
const checks = {
  'local-supervisor': ['Room supervisor', 'If this fails, refresh after starting the node. Saved rooms are preserved.'],
  'HTTPS-profile-and-identity': ['Public room HTTPS', 'Checks this node’s public profile and service identity through its local host route.'],
  'WSS-authentication-challenge': ['Room message connection', 'Checks that the message relay asks clients to authenticate.'],
  'local-DNS': ['Node and TURN hostnames', 'Checks DNS from this node. DNS on another network can differ.'],
  'storage-reserve': ['Free disk reserve', 'If this fails, free space on the host before more messages arrive.'],
  'STUN-UDP-34790': ['TURN over UDP · 34790', 'Local STUN response on the node’s UDP listener.'],
  'STUN-TCP-34790': ['TURN over TCP · 34790', 'Local STUN response on the node’s TCP listener.'],
  'STUN-TLS-53499': ['TURN over TLS · 53499', 'Local STUN response through the host’s TLS front.'],
  'STUN-TLS-443': ['TURN over TLS · 443', 'Uses turn. plus the node hostname. Intended for networks that block other ports.']
}
const navPages = ['Overview', 'Connections', 'Usage', 'Settings', 'Diagnostics']

function overview(status) {
  const services = status.services ?? []
  return `<h3>What’s running</h3><ul class="services">${services.length ? services.map(service => `<li><div class="service-heading"><strong>${escape(service.label)}</strong>${badge(service.state)}</div><p class="muted">${escape(service.detail)}</p><dl class="service-meta">${row('Version', escape(service.version ?? 'Not reported'))}${row('Uptime', uptime(service.uptimeSeconds))}</dl></li>`).join('') : '<li>Service details are unavailable. Refresh these controls.</li>'}</ul>
    <h3>Room access</h3><dl class="facts">${fact('Hosted rooms', count(status.rooms))}${fact('Devices with access', count(status.devices))}${fact('Pending operations', count(status.pending))}${fact('Your KithMoot account', status.paired ? 'Paired' : 'Unpaired')}</dl>
    <p class="muted">Access includes offline devices. A device in two rooms is counted twice. Open a room in KithMoot to see who is there now. Pending operations can include unfinished changes; they are not a count of people waiting to join.</p>
    <div class="actions">${status.deleting ? '<button class="primary" data-action="cancel-delete">Cancel deletion</button>' : status.running ? `<button class="primary" data-action="pair" ${status.ready ? '' : 'disabled'}>${status.paired ? 'Pair KithMoot on another device' : 'Pair with KithMoot'}</button><button data-action="pause">Pause node</button>` : '<button class="primary" data-action="start">Start node</button>'}</div>
    <p class="muted action-note">Pausing ends calls and makes rooms unavailable. Saved rooms and messages stay on the node.</p>`
}

function connections(status) {
  const connection = status.connections
  return `<h3>Connections</h3><dl class="details">${row('Archy controls', 'Private HTTPS · 3753', 'Your private route to Archy is needed to open these controls. A VPN or Wi-Fi change can break that route without stopping calls.')}${row('Rooms and messages', escape('https://' + status.host) + ' · 443', 'Public room access requires admission. The Archy dashboard and signer remain private.')}${row('TURN hostname', escape('turn.' + status.host), 'TURN over TLS on 443 uses this separate hostname.')}${row('Certificate expires', date(connection?.certificateValidUntil), 'Observed through this node’s local TLS route with certificate verification enabled.')}</dl>
    <h3>Local connection checks</h3><p class="muted">Checked ${date(connection?.checkedAt)}. These checks run from the node. Passing them does not prove calls work from another network.</p>${checkList(connection?.checks)}
    <div class="callout"><h3>Outside-network calls</h3><p>Not measured by these controls. Test an admitted audio/video call from another network, including a VPN or restrictive connection, to confirm authenticated TURN and media. TLS on 443 helps where UDP is blocked; it cannot guarantee every network permits calls.</p></div>`
}

function usage(status) {
  const usage = status.usage ?? {}, limits = status.limits ?? {}
  return `<h3>Usage</h3><p class="muted">Sampled ${date(usage.sampledAt)}. Container CPU and memory cover the controls, supervisor and both relays.</p><dl class="facts">
    ${fact('Container CPU', known(usage.cpuPercent) ? count(usage.cpuPercent) + '%' : 'Unavailable', '100% means one CPU core. The first sample needs a second reading.')}
    ${fact('Container memory', bytes(usage.memoryBytes), 'Limit: ' + bytes(usage.memoryLimitBytes))}
    ${fact('Room message storage', bytes(usage.storeBytes), 'Limit: ' + bytes(limits.maxBytes))}
    ${fact('Free space on data filesystem', bytes(usage.freeBytes), 'Keep free: ' + bytes(limits.minFreeBytes))}</dl>
    <dl class="details">${row('CPU allowance', known(usage.cpuLimitCores) ? count(usage.cpuLimitCores) + ' cores' : 'Not reported')}${row('Hosted rooms', `${count(status.rooms)} / ${count(limits.maxRooms)}`)}${row('Call bandwidth', 'Not measured', 'Configured total limit: ' + bandwidth(limits.aggregateBytesPerSecond) + '. This is a cap, not measured traffic.')}${row('TURN allocations', 'Not reported', 'An allocation is a relay connection, not a person. Reconnecting can temporarily use more than one.')}</dl>
    <p class="muted">Unavailable counters are not zero. Video quality, jitter and frozen frames must be measured in the calling apps. This view does not collect call content or participant IP addresses.</p>`
}

function bandwidth(value) { return known(value) ? count(value * 8 / 1000000) + ' Mbit/s' : 'Unavailable' }
function settings(status) {
  const limits = status.limits ?? {}
  return `<h3>Saved settings</h3><dl class="details">${row('Hosted room limit', count(limits.maxRooms))}${row('Total call bandwidth limit', bandwidth(limits.aggregateBytesPerSecond))}${row('Message storage limit', bytes(limits.maxBytes))}${row('Free disk reserve', bytes(limits.minFreeBytes))}${row('Call route', 'Through this node by default', 'Room members do not need to reveal their IP addresses to each other.')}${row('Room files', 'Unavailable in node rooms')}${row('TURN login lifetime', 'At most 5 minutes')}${row('Hosting', 'Away from home', 'Confirmed during setup. A public IP alone does not establish where a server is hosted.')}</dl>
    <p class="muted">Limits are chosen during setup. This version shows the saved values; changing limits here is not yet supported. Keep the saved data when reviewing the host configuration.</p>
    <h3>Account and data</h3><p>Pair KithMoot on your browser, computer or phone from Overview. Removing someone and closing a room happen in KithMoot. The node holds no room keys.</p><div class="actions"><button class="danger" data-action="delete" ${status.deleting ? 'disabled' : ''}>Delete everything…</button></div>`
}

function checkList(values = []) {
  return `<ul class="checks">${Object.entries(checks).map(([name, [title, detail]]) => `<li><div class="service-heading"><strong>${title}</strong>${badge(values.find(check => check.name === name)?.state)}</div><p class="muted">${detail}</p></li>`).join('')}</ul>`
}
function diagnostics(status) {
  const problem = status.diagnostics?.problem
  const text = problem === 'supervisor-unavailable' ? 'The room supervisor did not return a usable status. Saved data is preserved. Refresh, then check the Archy app status if it still cannot respond.'
    : problem === 'local-checks-incomplete' ? 'One or more local checks failed or could not be confirmed. Review the checks below and refresh after fixing the cause.'
      : status.deleting ? 'Deletion is prepared. New room access is blocked.' : !status.running ? 'The node is stopped. Start it from Overview to run service checks.' : status.ready ? 'All required local checks passed.' : 'Local readiness has not been confirmed.'
  return `<h3>Diagnostics</h3><p>${text}</p><p class="muted">Last service check: ${date(status.diagnostics?.checkedAt)}. Refresh reuses checks for up to 15 seconds.</p>${checkList(status.diagnostics?.checks)}
    <h3>Support report</h3><p>Copy the current summary to share with someone you trust. It includes the public node hostname, aggregate counts, limits and local check results. It excludes pairing links, sign-in tokens, identities, room identifiers, messages and participant addresses.</p><div class="actions"><button data-action="copy-diagnostics">Copy diagnostics</button></div><p class="muted action-note">No history is stored or sent automatically. This report does not include an outside-network call test.</p>`
}

export function supportReport(status) {
  return JSON.stringify({ v: 1, host: status.host, observedAt: status.observedAt, configured: status.configured, running: status.running,
    ready: status.ready, deleting: status.deleting, rooms: status.rooms, devices: status.devices, pending: status.pending,
    limits: status.limits, services: status.services, connections: status.connections, usage: status.usage, diagnostics: status.diagnostics }, null, 2)
}

export function dashboard(status, page) {
  const label = status.deleting ? 'Prepared for deletion' : status.ready ? 'Locally ready' : status.running ? 'Needs attention' : status.paused ? 'Paused' : 'Stopped'
  const render = { overview, connections, usage, settings, diagnostics }[page] ?? overview
  return `<span class="badge ${status.ready ? 'ready' : ''}">${label}</span><h2 class="host">${escape(status.host)}</h2><p class="muted">${status.deleting ? 'New rooms and requests are blocked. Return to Archy to delete the app and its data, or cancel from Overview.' : status.ready ? 'Local checks passed. Outside-network calls need their own test.' : status.running ? 'The node is running. Open Diagnostics for its local checks.' : 'Start the node to make hosted rooms and calls available again.'}</p>
    <nav class="dashboard-nav" aria-label="Node views">${navPages.map(title => `<button data-page="${title.toLowerCase()}" ${page === title.toLowerCase() ? 'aria-current="page"' : ''}>${title}</button>`).join('')}</nav>
    <div class="dashboard-panel">${render(status)}</div><div class="actions dashboard-footer"><button data-action="refresh">Refresh status</button><button data-action="sign-out">Sign out</button></div><p class="muted action-note">Status received ${date(status.observedAt)}. The controls sign out after 30 minutes without use. Rooms and calls keep running.</p>`
}
