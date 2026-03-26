const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
let _events = [];
let _noteId = null;
let _timer = null;

export function initAuditLog(noteId) {
  _noteId = noteId;
}

export function logEvent(type, details = {}) {
  _events.push({ ts: new Date().toISOString(), type, details });
  if (_timer) clearTimeout(_timer);
  _timer = setTimeout(flushEvents, 1000);
}

async function flushEvents() {
  if (!_noteId || _events.length === 0) return;
  const batch = _events.splice(0, _events.length);
  try {
    await fetch(`${API_BASE}/save-audit-log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note_id: _noteId, events: batch }),
    });
  } catch (err) {
    // Re-add failed events for next flush.
    _events.unshift(...batch);
  }
}

// Flush on page unload.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    if (_noteId && _events.length > 0) {
      const payload = JSON.stringify({ note_id: _noteId, events: _events });
      navigator.sendBeacon(`${API_BASE}/save-audit-log`, payload);
    }
  });
}
