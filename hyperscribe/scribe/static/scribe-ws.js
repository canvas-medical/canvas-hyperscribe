/**
 * Scribe WebSocket — real-time updates for note state changes and audit events.
 * Usage: const cleanup = connectScribeWS(noteId, onMessage);
 */
export function connectScribeWS(noteId, onMessage) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/plugin-io/ws/hyperscribe/scribe-${noteId}/`;

  let ws = null;
  let reconnectTimer = null;
  let closed = false;

  function connect() {
    if (closed) return;
    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('[scribe-ws] connected');
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed.message) {
          onMessage(parsed.message);
        }
      } catch (err) {
        console.error('[scribe-ws] parse error:', err);
      }
    };

    ws.onclose = () => {
      if (!closed) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => { ws.close(); };
  }

  connect();

  const pingInterval = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 30000);

  return () => {
    closed = true;
    clearInterval(pingInterval);
    clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}
