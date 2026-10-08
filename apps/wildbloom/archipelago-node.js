/* Archipelago package integration. No discovery, persistence or network I/O. */
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('blossom-server');
  const profiles = [...document.querySelectorAll('input[name="network-profile"]')];
  if (!input || !profiles.length) return;
  let own;
  try {
    own = new URL(window.ARCHIPELAGO_NODE_ORIGIN || location.href);
    if (!window.ARCHIPELAGO_NODE_ORIGIN) {
      own.port = '3742';
      own.pathname = '/';
      own.search = '';
      own.hash = '';
    }
    if (own.protocol !== 'https:' || own.username || own.password || own.search || own.hash
      || own.pathname !== '/' || own.hostname.endsWith('.onion')) return;
  } catch { return; }
  const home = own.origin;
  const help = document.getElementById('blossom-help');
  if (help) help.textContent = 'Your Archipelago node is selected by default. You can choose another storage destination.';
  const notice = document.querySelector('#client .byo-notice');
  if (notice) notice.textContent = 'Your Archipelago node is the default storage destination. Files go directly from your browser to the storage you choose. Relays and extra copies remain your choice.';
  const introduction = document.getElementById('connection-heading')?.nextElementSibling;
  if (introduction) introduction.textContent = 'Start with your own node. You decide which other services learn about the file.';
  const controls = document.createElement('div');
  controls.className = 'layout-summary';
  const status = document.createElement('p');
  status.id = 'archipelago-node-status';
  status.setAttribute('role', 'status');
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Use my Archipelago node';
  button.id = 'archipelago-use-node';
  controls.append(status, button);
  input.closest('.grid')?.after(controls);
  if (!controls.isConnected) input.after(controls);
  const direct = () => profiles.some(p => p.checked && p.value === 'direct');
  const update = () => {
    button.disabled = !direct() || input.disabled;
    status.textContent = !direct()
      ? 'My Archipelago node is an HTTPS destination. Choose an onion destination for Tor-only mode.'
      : input.disabled
        ? `My Archipelago node: ${home}. Choose each pool destination explicitly.`
        : input.value.replace(/\/$/, '') === home
        ? `My node: ${home}. Uploads stay here unless you choose another destination.`
        : `My Archipelago node: ${home}. You have selected another destination or storage layout.`;
  };
  const select = () => {
    if (!direct() || input.disabled) return;
    input.value = home;
    // The upstream listener revokes all prior endpoint/signing consent.
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };
  button.addEventListener('click', select);
  input.addEventListener('input', update);
  for (const radio of profiles) radio.addEventListener('change', () => {
    if (direct() && !input.value) select();
    update();
  });
  document.getElementById('storage-mode')?.addEventListener('input', update);
  // Initial selection happens before any user action; avoid presenting a
  // misleading "service cleared" warning on first open.
  if (!input.value && direct() && !input.disabled) input.value = home;
  update();
});
