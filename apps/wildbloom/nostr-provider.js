/**
 * NIP-07 Nostr Provider Shim — Archipelago
 *
 * In an Archipelago iframe, requests go directly to the parent dashboard.
 * In a browser tab or companion WebView, a dashboard-origin signer frame
 * supplies the same identity picker and consent UI. No opener is required,
 * and private keys never leave the node backend.
 */
(function () {
  'use strict';
  if (window.__archipelagoNostr) return;
  window.__archipelagoNostr = true;

  var providerScript = document.currentScript;
  var autoNip98 = !(providerScript && providerScript.hasAttribute('data-no-nip98'));
  var embedded = window !== window.top;
  var pending = {}, rentalPending = {}, mediaPending = {}, nextId = 1, queuedMessages = [];
  var identitySelection = null;
  var selectedIdentity = null, identitySubscribers = [];
  var selectedPublicKey = null, selectedPublicKeyTimer = null;
  var signerFrame = null, signerReady = embedded, signerInitialised = embedded;
  var signerVisible = false, signerHideWaiters = [];
  var appReady = embedded || document.readyState === 'complete';

  function dashboardOrigin() {
    var url = new URL(window.location.href);
    url.port = '';
    return url.origin;
  }

  function inferAppId() {
    var configured = providerScript && providerScript.getAttribute('data-app-id');
    if (configured) return configured;
    var route = window.location.pathname.match(/^\/app\/([a-z0-9._-]+)(?:\/|$)/i);
    if (route) return route[1].toLowerCase();
    var ports = { '7778': 'indeedhub', '8337': 'archipelago-source' };
    return ports[window.location.port] || ('app-' + (window.location.port || 'dashboard'));
  }

  function sendToSignerFrame(message) {
    if (!signerFrame || !signerFrame.contentWindow) return;
    signerFrame.contentWindow.postMessage(message, dashboardOrigin());
  }

  function postToSigner(message) {
    if (embedded) {
      window.parent.postMessage(message, '*');
      return;
    }
    if (!signerFrame) createSignerFrame();
    // A loaded iframe is not yet an initialised signer. Requests that arrive
    // while the host app is still booting must follow signer-init, otherwise
    // the signer correctly rejects them because it has no app id/origin yet.
    if (!signerReady || !signerInitialised || !signerFrame || !signerFrame.contentWindow) {
      queuedMessages.push(message);
      return;
    }
    sendToSignerFrame(message);
  }

  function setSignerVisible(visible) {
    if (!signerFrame) return;
    signerVisible = visible;
    signerFrame.style.display = 'block';
    signerFrame.style.visibility = 'visible';
    signerFrame.style.pointerEvents = visible ? 'auto' : 'none';
    signerFrame.style.opacity = visible ? '1' : '0';
    signerFrame.style.top = '0';
    signerFrame.style.left = '0';
    signerFrame.style.width = visible ? '100vw' : '1px';
    signerFrame.style.height = visible ? '100vh' : '1px';
    signerFrame.style.transform = visible ? 'none' : 'translate(-10000px, -10000px)';
    signerFrame.setAttribute('aria-hidden', visible ? 'false' : 'true');
    if (!visible && signerHideWaiters.length) {
      var waiters = signerHideWaiters.splice(0);
      waiters.forEach(function (resolve) { resolve(); });
    }
  }

  // NIP-98 returns before the signer's short success animation has closed.
  // Reloading an Android WebView while that topmost cross-origin frame is
  // still visible can leave a blank compositor surface until the user reloads
  // again. Let the broker finish and hide first, with a bounded fallback so a
  // lost UI message can never prevent authentication from completing.
  function waitForSignerToHide() {
    if (embedded || !signerVisible) return Promise.resolve();
    return new Promise(function (resolve) {
      var settled = false;
      function finish() {
        if (settled) return;
        settled = true;
        resolve();
      }
      signerHideWaiters.push(finish);
      setTimeout(finish, 1500);
    });
  }

  function createSignerFrame() {
    if (embedded || signerFrame) return;
    signerFrame = document.createElement('iframe');
    signerFrame.id = 'archipelago-nostr-signer';
    signerFrame.title = 'Archipelago Nostr signer';
    signerFrame.src = dashboardOrigin() + '/nostr-signer';
    // Keep the broker document alive between requests, but park its compositor
    // surface physically off-screen. Removing or display-hiding a full-screen
    // cross-origin iframe can leave Android WebView (and some mobile Chromium
    // builds) showing that stale black/grey surface until a manual refresh.
    // A 1px off-screen frame cannot obscure the app and also avoids reloading
    // the signer between getPublicKey/signEvent calls.
    signerFrame.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;transform:translate(-10000px,-10000px);border:0;z-index:2147483647;background:transparent;display:block;visibility:visible;opacity:0;pointer-events:none;';
    signerFrame.setAttribute('aria-hidden', 'true');
    document.documentElement.appendChild(signerFrame);
  }

  function initialiseSignerWhenReady() {
    if (embedded || signerInitialised || !signerReady || !appReady) return;
    sendToSignerFrame({
      type: 'archipelago:signer-init',
      appId: inferAppId(),
      appName: (document.title || 'App').replace(/\s*[|—-]\s*Archipelago\s*$/i, ''),
    });
    signerInitialised = true;
    while (queuedMessages.length) sendToSignerFrame(queuedMessages.shift());
  }

  function request(method, params) {
    return new Promise(function (resolve, reject) {
      var id = nextId++;
      pending[id] = { resolve: resolve, reject: reject };
      postToSigner({ type: 'nostr-request', id: id, method: method, params: params || {} });
      setTimeout(function () {
        if (pending[id]) {
          pending[id].reject(new Error('NIP-07 timeout'));
          delete pending[id];
        }
      }, 30000);
    });
  }

  // Archipelago-aware apps can call this immediately before an explicit login
  // action. Standard NIP-07 intentionally has no "choose account" method, so
  // getPublicKey() alone cannot distinguish a fresh login from a routine signer
  // call. Keeping this as an optional companion API preserves NIP-07 compatibility
  // while allowing users to change their node identity when they log in again.
  function selectIdentity() {
    autoAuthSuspended = false;
    if (identitySelection) {
      identitySelection.reject(new Error('A node identity choice is already open'));
      clearTimeout(identitySelection.timer);
    }
    return new Promise(function (resolve, reject) {
      var timer = setTimeout(function () {
        if (!identitySelection) return;
        identitySelection = null;
        reject(new Error('Identity selection timed out'));
      }, 30000);
      identitySelection = { resolve: resolve, reject: reject, timer: timer };
      postToSigner({
        type: embedded
          ? 'archipelago:identity:request'
          : 'archipelago:signer-select-identity',
        force: true,
      });
    });
  }

  // JWT claims are a reuse hint only; the API still verifies the signature.
  // Never let an unrelated or expired app session override the chosen node key.
  function tokenMatchesIdentity(token, pubkey) {
    try {
      if (typeof token !== 'string' || !pubkey) return false;
      var parts = token.split('.');
      if (parts.length !== 3 || !parts.every(function (part) { return /^[A-Za-z0-9_-]+$/.test(part); })) return false;
      var encoded = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      while (encoded.length % 4) encoded += '=';
      var claims = JSON.parse(atob(encoded));
      return claims.sub === pubkey && typeof claims.exp === 'number' &&
        Number.isFinite(claims.exp) && claims.exp > Date.now() / 1000;
    } catch (_) { return false; }
  }

  var authGeneration = 0, authAttempt = null, autoAuthTimer = null, autoAuthSuspended = false;
  function clearSession() {
    authGeneration++;
    authAttempt = null;
    clearTimeout(autoAuthTimer);
    autoAuthSuspended = true;
    var previous = selectedIdentity && selectedIdentity.nostr_pubkey;
    selectedIdentity = null; selectedPublicKey = null;
    clearTimeout(selectedPublicKeyTimer);
    window.dispatchEvent(new CustomEvent('archipelago:identity-changing', { detail: { nostr_pubkey: null, previous_nostr_pubkey: previous } }));
    // These are app session credentials, not stored accounts, profiles or keys.
    try {
      ['nostr_token', 'nostr_pubkey', 'refresh_token'].forEach(function (key) { sessionStorage.removeItem(key); });
    } catch (_) {}
    // Signing out is also an explicit request to stop the dashboard from
    // restoring this app's remembered identity on its next load. The broker
    // forgets only the app-to-identity selection; node identities and keys are
    // preserved and remain available for a later explicit sign-in.
    postToSigner({
      type: embedded
        ? 'archipelago:identity:clear'
        : 'archipelago:signer-clear-session',
    });
  }

  function scheduleIdentityAuth(pubkey) {
    if (!autoNip98 || autoAuthSuspended) return;
    try { if (tokenMatchesIdentity(sessionStorage.getItem('nostr_token'), pubkey)) return; } catch (_) {}
    clearTimeout(autoAuthTimer);
    var generation = authGeneration;
    autoAuthTimer = setTimeout(function () {
      if (generation === authGeneration && selectedIdentity && selectedIdentity.nostr_pubkey === pubkey) doNip98Auth(pubkey, generation);
    }, 1500);
  }

  function finishIdentitySelection(identity) {
    // The identity picker is itself an explicit choice to disclose this key.
    // Keep it briefly so the login library's immediately-following
    // getPublicKey() does not depend on another cross-origin WebView round trip.
    // This is deliberately one-shot and short-lived.
    if (identity && typeof identity.nostr_pubkey === 'string' && /^[0-9a-f]{64}$/.test(identity.nostr_pubkey)) {
      var previous = selectedIdentity && selectedIdentity.nostr_pubkey;
      var changed = previous !== identity.nostr_pubkey;
      var storedToken = null;
      try { storedToken = sessionStorage.getItem('nostr_token'); } catch (_) {}
      var invalidSession = !!storedToken && !tokenMatchesIdentity(storedToken, identity.nostr_pubkey);
      selectedIdentity = { nostr_pubkey: identity.nostr_pubkey };
      var displayName = identity.display_name || identity.name;
      if (typeof displayName === 'string' && displayName.trim()) selectedIdentity.display_name = displayName.trim().slice(0, 160);
      if (changed || (invalidSession && !authAttempt)) {
        authGeneration++;
        authAttempt = null;
        clearTimeout(autoAuthTimer);
        window.dispatchEvent(new CustomEvent('archipelago:identity-changing', { detail: {
          nostr_pubkey: identity.nostr_pubkey, previous_nostr_pubkey: previous,
        } }));
      }
      try {
        if (!tokenMatchesIdentity(sessionStorage.getItem('nostr_token'), identity.nostr_pubkey)) {
          ['nostr_token', 'nostr_pubkey', 'refresh_token'].forEach(function (key) { sessionStorage.removeItem(key); });
        } else {
          if (sessionStorage.getItem('nostr_pubkey') !== identity.nostr_pubkey) sessionStorage.removeItem('refresh_token');
          sessionStorage.setItem('nostr_pubkey', identity.nostr_pubkey);
        }
      } catch (_) {}
      selectedPublicKey = identity.nostr_pubkey;
      clearTimeout(selectedPublicKeyTimer);
      selectedPublicKeyTimer = setTimeout(function () {
        selectedPublicKey = null;
        selectedPublicKeyTimer = null;
      }, 15000);
      scheduleIdentityAuth(identity.nostr_pubkey);
      identitySubscribers.slice().forEach(function (subscriber) {
        try { subscriber(getSelectedIdentity()); } catch (error) {
          console.error('[nostr-provider] identity listener failed:', error);
        }
      });
    }
    if (!identitySelection) return;
    var selection = identitySelection;
    identitySelection = null;
    clearTimeout(selection.timer);
    if (!identity || !/^[0-9a-f]{64}$/.test(identity.nostr_pubkey)) selection.reject(new Error('Invalid native public key'));
    else selection.resolve(getSelectedIdentity());
  }

  function cancelIdentitySelection() {
    if (!identitySelection) return;
    var selection = identitySelection;
    identitySelection = null;
    clearTimeout(selection.timer);
    selection.reject(new Error('Identity selection cancelled'));
  }

  function getPublicKey() {
    // Most NIP-07 apps call getPublicKey directly from their login button. A
    // live user activation lets the node offer account switching to those apps
    // without making background account restoration reopen the picker. Apps
    // with an async login flow should call archipelagoNostr.selectIdentity()
    // explicitly; its result is consumed here so the picker is not shown twice.
    if (selectedPublicKey) {
      var publicKey = selectedPublicKey;
      selectedPublicKey = null;
      clearTimeout(selectedPublicKeyTimer);
      selectedPublicKeyTimer = null;
      return Promise.resolve(publicKey);
    }
    // The picker click itself leaves transient user activation active. A second
    // public-key lookup in the same login must not open another picker.
    var restoringSession = false;
    try {
      var sessionHint = sessionStorage.getItem('nostr_token');
      restoringSession = !!selectedIdentity && tokenMatchesIdentity(sessionHint, selectedIdentity.nostr_pubkey);
    } catch (_) {}
    // This is only a UI hint: the broker still verifies the node session and
    // signing permissions. A restored app token never authorizes a signature.
    if (!restoringSession && !selectedIdentity && navigator.userActivation && navigator.userActivation.isActive) {
      return selectIdentity().then(function () {
        return getPublicKey();
      });
    }
    return request('getPublicKey');
  }

  // Framework components often mount just after the provider receives the
  // eager first-launch identity. A sticky subscription prevents that choice
  // from being lost between window.load and React/Vue effect registration.
  function onIdentitySelected(subscriber) {
    if (typeof subscriber !== 'function') {
      throw new TypeError('Identity subscriber must be a function');
    }
    identitySubscribers.push(subscriber);
    if (selectedIdentity) {
      try { subscriber(getSelectedIdentity()); } catch (error) {
        console.error('[nostr-provider] identity listener failed:', error);
      }
    }
    return function () {
      identitySubscribers = identitySubscribers.filter(function (entry) {
        return entry !== subscriber;
      });
    };
  }

  function getSelectedIdentity() {
    return selectedIdentity && Object.assign({}, selectedIdentity);
  }

  window.addEventListener('message', function (e) {
    var validSource = embedded
      ? e.source === window.parent && e.origin === dashboardOrigin()
      : signerFrame && e.source === signerFrame.contentWindow && e.origin === dashboardOrigin();
    if (!validSource || !e.data) return;

    if (!embedded && e.data.type === 'archipelago:signer-ready') {
      signerReady = true;
      initialiseSignerWhenReady();
      return;
    }
    if (!embedded && e.data.type === 'archipelago:signer-show') {
      setSignerVisible(true);
      return;
    }
    if (!embedded && e.data.type === 'archipelago:signer-hide') {
      setSignerVisible(false);
      return;
    }
    if (!embedded && e.data.type === 'archipelago:signer-identity') {
      finishIdentitySelection(e.data.identity);
      window.postMessage({
        type: 'archipelago:identity',
        nostr_pubkey: selectedIdentity && selectedIdentity.nostr_pubkey,
        display_name: selectedIdentity && selectedIdentity.display_name,
      }, window.location.origin);
      return;
    }
    if (embedded && e.data.type === 'archipelago:identity') {
      finishIdentitySelection(e.data);
      return;
    }
    if (e.data.type === 'archipelago:identity-cancelled' ||
        e.data.type === 'archipelago:signer-identity-cancelled') {
      cancelIdentitySelection();
      return;
    }
    if (e.data.type === 'archipelago-rental-response') {
      var rental = rentalPending[e.data.id];
      if (!rental) return;
      delete rentalPending[e.data.id]; clearTimeout(rental.timer); rental.cleanup();
      e.data.error ? rental.reject(new Error(e.data.error)) : rental.resolve(e.data.result);
      return;
    }
    if (e.data.type === 'archipelago-media-registration-response') {
      var media = mediaPending[e.data.id];
      if (!media) return;
      delete mediaPending[e.data.id];
      clearTimeout(media.timer);
      e.data.error ? media.reject(new Error(e.data.error)) : media.resolve(e.data.result);
      return;
    }
    if (e.data.type !== 'nostr-response') return;
    var handler = pending[e.data.id];
    if (!handler) return;
    delete pending[e.data.id];
    e.data.error ? handler.reject(new Error(e.data.error)) : handler.resolve(e.data.result);
  });

  window.nostr = {
    getPublicKey: getPublicKey,
    signEvent: function (event) { return request('signEvent', { event: event }); },
    sign: function (event) { return request('signEvent', { event: event }); },
    getRelays: function () { return request('getRelays'); },
    nip04: {
      encrypt: function (pubkey, plaintext) { return request('nip04.encrypt', { pubkey: pubkey, plaintext: plaintext }); },
      decrypt: function (pubkey, ciphertext) { return request('nip04.decrypt', { pubkey: pubkey, ciphertext: ciphertext }); },
    },
    nip44: {
      encrypt: function (pubkey, plaintext) { return request('nip44.encrypt', { pubkey: pubkey, plaintext: plaintext }); },
      decrypt: function (pubkey, ciphertext) { return request('nip44.decrypt', { pubkey: pubkey, ciphertext: ciphertext }); },
    },
  };

  // Exact owner-approved Cloud registration. The dashboard checks the installed
  // app origin/audience and displays the native picker before any preparation.
  function nativeRequestId() {
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    // Secure randomness remains available on ordinary HTTP node/LAN origins.
    var bytes = new Uint8Array(16); crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    var hex = Array.from(bytes, function (value) { return value.toString(16).padStart(2, '0'); }).join('');
    return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);
  }

  function rentalRequest(action, payload, timeout, signal) {
    return new Promise(function (resolve, reject) {
      if (signal && (typeof signal.addEventListener !== 'function' || typeof signal.removeEventListener !== 'function' || typeof signal.aborted !== 'boolean')) { reject(new Error('Invalid rental cancellation signal.')); return; }
      if (signal && signal.aborted) { reject(new Error('Rental request closed.')); return; }
      var id = nativeRequestId();
      function cleanup() { if (signal) signal.removeEventListener('abort', abort); }
      function fail(message) {
        var pending = rentalPending[id]; if (!pending) return;
        delete rentalPending[id]; clearTimeout(pending.timer); cleanup();
        if (action === 'request') postToSigner({type:'archipelago-rental-request',id:id,action:'cancel',playbackProtocol:2});
        reject(new Error(message));
      }
      function abort() { fail('Rental request closed. Recover any dispatched payment using the original purchase.'); }
      rentalPending[id] = { resolve: resolve, reject: reject, cleanup: cleanup, timer: setTimeout(function () {
        fail('Rental response unavailable. Recover the same purchase without paying again.');
      }, timeout) };
      if (signal) signal.addEventListener('abort', abort, {once:true});
      postToSigner(Object.assign({ type: 'archipelago-rental-request', id: id, action: action, playbackProtocol: 2 }, payload));
    });
  }
  window.archipelagoRental = {
    status: function (handle) { return rentalRequest('status', { handle: handle }, 35000); },
    prepare: function (handle, retry) { return rentalRequest('prepare', { handle: handle, retry: retry === true }, 35000); },
    start: function (handle, readyId) { return rentalRequest('start', { handle: handle, ready_id: readyId }, 35000); },
    request: function (offer, options) {
      if (!options || options.playbackProtocol !== 2) return Promise.reject(new Error('Playback protocol 2 is required before requesting a rental.'));
      if (options.renewExpired !== undefined && typeof options.renewExpired !== 'boolean') return Promise.reject(new Error('Invalid rental renewal request.'));
      return rentalRequest('request', { offer: offer, renewExpired: options.renewExpired === true }, 600000, options.signal);
    }
  };
  Object.defineProperty(window.archipelagoRental, 'playbackProtocol', { value: 2, writable: false, configurable: false, enumerable: true });

  window.archipelagoMediaRegistration = {
    request: function (action, payload) {
      if (['select', 'resume', 'submit', 'complete', 'resolve', 'resolve-submit'].indexOf(action) === -1 || !payload || typeof payload !== 'object') {
        return Promise.reject(new Error('Invalid native media registration request'));
      }
      return new Promise(function (resolve, reject) {
        var id = nativeRequestId();
        mediaPending[id] = { resolve: resolve, reject: reject, timer: setTimeout(function () {
          var item = mediaPending[id];
          if (!item) return;
          delete mediaPending[id];
          item.reject(new Error('Registration was not confirmed. Resume the same saved operation.'));
        }, 600000) };
        postToSigner({ type: 'archipelago-media-registration-request', id: id, action: action,
          intent: payload.intent, selection: payload.selection, approvalId: payload.approvalId,
          producerEvent: payload.producerEvent });
      });
    },
  };

  window.archipelagoNostr = {
    selectIdentity: selectIdentity,
    onIdentitySelected: onIdentitySelected,
    getSelectedIdentity: getSelectedIdentity,
    clearSession: clearSession,
  };

  // Optional direct NIP-98 session bootstrap for apps that use it. Signing
  // itself is shown by the shared broker, so this deliberately adds no second
  // full-screen loader inside the app.
  function doNip98Auth(pubkey, generation) {
    if (authAttempt || autoAuthSuspended) return;
    var attempt = {};
    authAttempt = attempt;
    function current() {
      return authAttempt === attempt && generation === authGeneration && !autoAuthSuspended &&
        selectedIdentity && selectedIdentity.nostr_pubkey === pubkey;
    }
    function requireCurrent() { if (!current()) throw new Error('Identity choice changed'); }
    var healthUrl = window.location.origin + '/api/nostr-auth/health';
    var sessionUrl = window.location.origin + '/api/auth/nostr/session';
    var healthController = new AbortController();
    var healthTimeout = setTimeout(function () { healthController.abort(); }, 3000);

    fetch(healthUrl, { signal: healthController.signal }).then(function (response) {
      clearTimeout(healthTimeout);
      requireCurrent();
      if (!response.ok) throw new Error('Health ' + response.status);
      return window.nostr.signEvent({
        kind: 27235,
        created_at: Math.floor(Date.now() / 1000),
        content: '',
        pubkey: pubkey,
        tags: [['u', sessionUrl], ['method', 'POST']],
      });
    }).then(function (signed) {
      requireCurrent();
      if (!signed || signed.pubkey !== pubkey) throw new Error('Signer identity differs from selected identity');
      var controller = new AbortController();
      setTimeout(function () { controller.abort(); }, 10000);
      return fetch(sessionUrl, {
        method: 'POST',
        headers: { 'Authorization': 'Nostr ' + btoa(JSON.stringify(signed)) },
        signal: controller.signal,
      });
    }).then(function (response) {
      if (!response.ok) throw new Error('Auth failed: ' + response.status);
      return response.json();
    }).then(function (data) {
      requireCurrent();
      if (!tokenMatchesIdentity(data.accessToken, pubkey)) throw new Error('Authentication returned an expired or differently bound session');
      sessionStorage.setItem('nostr_token', data.accessToken);
      sessionStorage.setItem('nostr_pubkey', pubkey);
      if (data.refreshToken) sessionStorage.setItem('refresh_token', data.refreshToken);
      else sessionStorage.removeItem('refresh_token');
      return waitForSignerToHide().then(function () {
        // Give WebView one paint after the iframe is hidden before replacing
        // the document. The stored session is already durable at this point.
        return new Promise(function (resolve) {
          window.requestAnimationFrame(function () {
            window.requestAnimationFrame(resolve);
          });
        });
      }).then(function () {
        requireCurrent();
        if (window.ArchipelagoSurface &&
            typeof window.ArchipelagoSurface.expectPageTransition === 'function') {
          window.ArchipelagoSurface.expectPageTransition();
        }
        window.location.reload();
      });
    }).catch(function (error) {
      if (authAttempt === attempt) authAttempt = null;
      var message = error && error.message ? error.message : String(error);
      if (message.toLowerCase().indexOf('abort') > -1) message = 'API timeout';
      console.warn('[nostr-provider] NIP-98 skipped:', message);
    });
  }

  // Only identity-aware apps open the chooser eagerly. The provider is also
  // injected into several ordinary app proxies; those stay untouched unless
  // they actually invoke a NIP-07 method, which lazily creates the broker.
  if (!embedded && ['indeedhub', 'nostrudel', 'archipelago-source'].indexOf(inferAppId()) !== -1) {
    createSignerFrame();
  }

  // The provider is injected in <head>, before framework startup. Waiting for
  // load makes the first-launch picker meaningful: React/Vue login listeners
  // and account stores exist before a fast identity choice can be emitted.
  if (!embedded && !appReady) {
    window.addEventListener('load', function () {
      appReady = true;
      initialiseSignerWhenReady();
    }, { once: true });
  }
})();
