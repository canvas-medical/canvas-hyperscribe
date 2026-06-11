/*
 * mock-io.js — stubs the Canvas <-> iframe IO seams so the real Scribe
 * components can boot in a plain browser.
 *
 * Classic script (no imports) so it runs BEFORE any deferred module script,
 * guaranteeing the stubs are in place before the Scribe component mounts.
 *
 * Two seams:
 *   1. window.__canvasPort()  — the MessagePort the real index.html captures
 *      from Canvas. Components post RESIZE / CLOSE_MODAL / NOTE_TAB_CHANGE here.
 *   2. window.WebSocket       — scribe-ws.js opens a note-state socket on mount;
 *      with no backend it would error+reconnect forever. We replace it with an
 *      inert stub that simply never opens (no errors, no reconnect spam).
 */
(function () {
  'use strict';

  // ---- 1. Fake MessagePort -------------------------------------------------
  const fakePort = {
    postMessage(msg) {
      // Surface outbound messages for debugging; Canvas would normally act on these.
      if (window.__MOCK_LOG_PORT) console.debug('[mock-io] port.postMessage', msg);
    },
    start() {},
    close() {},
    addEventListener() {},
    removeEventListener() {},
    onmessage: null,
  };
  window.__canvasPort = function () { return fakePort; };

  // Let harness code inject inbound canvas-message events (e.g. NOTE_TAB_CHANGE,
  // NOTE_STATE_CHANGE) the way Canvas would via the MessagePort bridge.
  window.__mockCanvasMessage = function (data) {
    window.dispatchEvent(new CustomEvent('canvas-message', { detail: data }));
  };

  // ---- 2. Inert WebSocket --------------------------------------------------
  const RealWebSocket = window.WebSocket;
  function InertWebSocket(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING — and it stays there, quietly.
    this.onopen = this.onmessage = this.onclose = this.onerror = null;
  }
  InertWebSocket.prototype.send = function () {};
  InertWebSocket.prototype.close = function () { this.readyState = 3; };
  InertWebSocket.CONNECTING = 0;
  InertWebSocket.OPEN = 1;
  InertWebSocket.CLOSING = 2;
  InertWebSocket.CLOSED = 3;
  // Only intercept the scribe note-state socket; leave any other WS untouched.
  window.WebSocket = function (url, protocols) {
    if (typeof url === 'string' && url.includes('/plugin-io/ws/hyperscribe/')) {
      return new InertWebSocket(url);
    }
    return new RealWebSocket(url, protocols);
  };
  window.WebSocket.prototype = RealWebSocket.prototype;
  Object.assign(window.WebSocket, {
    CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3,
  });

  console.debug('[mock-io] IO seams stubbed (MessagePort + WebSocket)');
})();
