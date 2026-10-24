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
  var pending = {}, nextId = 1, queuedMessages = [];
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

  function finishIdentitySelection(identity) {
    // The identity picker is itself an explicit choice to disclose this key.
    // Keep it briefly so the login library's immediately-following
    // getPublicKey() does not depend on another cross-origin WebView round trip.
    // This is deliberately one-shot and short-lived.
    if (identity && typeof identity.nostr_pubkey === 'string' && identity.nostr_pubkey) {
      selectedIdentity = { nostr_pubkey: identity.nostr_pubkey };
      selectedPublicKey = identity.nostr_pubkey;
      clearTimeout(selectedPublicKeyTimer);
      selectedPublicKeyTimer = setTimeout(function () {
        selectedPublicKey = null;
        selectedPublicKeyTimer = null;
      }, 15000);
      identitySubscribers.slice().forEach(function (subscriber) {
        try { subscriber(selectedIdentity); } catch (error) {
          console.error('[nostr-provider] identity listener failed:', error);
        }
      });
    }
    if (!identitySelection) return;
    var selection = identitySelection;
    identitySelection = null;
    clearTimeout(selection.timer);
    selection.resolve(identity);
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
    if (navigator.userActivation && navigator.userActivation.isActive) {
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
      try { subscriber(selectedIdentity); } catch (error) {
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
    return selectedIdentity && { nostr_pubkey: selectedIdentity.nostr_pubkey };
  }

  window.addEventListener('message', function (e) {
    var validSource = embedded
      ? e.source === window.parent
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
        nostr_pubkey: e.data.identity && e.data.identity.nostr_pubkey,
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

  window.archipelagoNostr = {
    selectIdentity: selectIdentity,
    onIdentitySelected: onIdentitySelected,
    getSelectedIdentity: getSelectedIdentity,
  };

  // Optional direct NIP-98 session bootstrap for apps that use it. Signing
  // itself is shown by the shared broker, so this deliberately adds no second
  // full-screen loader inside the app.
  var authDone = false;

  function doNip98Auth(pubkey) {
    if (authDone) return;
    authDone = true;
    var healthUrl = window.location.origin + '/api/nostr-auth/health';
    var sessionUrl = window.location.origin + '/api/auth/nostr/session';
    var healthController = new AbortController();
    var healthTimeout = setTimeout(function () { healthController.abort(); }, 3000);

    fetch(healthUrl, { signal: healthController.signal }).then(function (response) {
      clearTimeout(healthTimeout);
      if (!response.ok) throw new Error('Health ' + response.status);
      return window.nostr.signEvent({
        kind: 27235,
        created_at: Math.floor(Date.now() / 1000),
        content: '',
        pubkey: pubkey,
        tags: [['u', sessionUrl], ['method', 'POST']],
      });
    }).then(function (signed) {
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
      if (!data.accessToken) throw new Error('Authentication returned no access token');
      sessionStorage.setItem('nostr_token', data.accessToken);
      sessionStorage.setItem('nostr_pubkey', pubkey);
      if (data.refreshToken) sessionStorage.setItem('refresh_token', data.refreshToken);
      return waitForSignerToHide().then(function () {
        // Give WebView one paint after the iframe is hidden before replacing
        // the document. The stored session is already durable at this point.
        return new Promise(function (resolve) {
          window.requestAnimationFrame(function () {
            window.requestAnimationFrame(resolve);
          });
        });
      }).then(function () {
        if (window.ArchipelagoSurface &&
            typeof window.ArchipelagoSurface.expectPageTransition === 'function') {
          window.ArchipelagoSurface.expectPageTransition();
        }
        window.location.reload();
      });
    }).catch(function (error) {
      authDone = false;
      var message = error && error.message ? error.message : String(error);
      if (message.toLowerCase().indexOf('abort') > -1) message = 'API timeout';
      console.warn('[nostr-provider] NIP-98 skipped:', message);
    });
  }

  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'archipelago:identity' || !autoNip98) return;
    if (e.source !== window && e.source !== window.parent) return;
    var pubkey = e.data.nostr_pubkey;
    if (!pubkey) return;
    try {
      var token = sessionStorage.getItem('nostr_token');
      if (token && token.indexOf('mock-') === -1) return;
    } catch (_) {}
    setTimeout(function () { doNip98Auth(pubkey); }, 1500);
  });

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
