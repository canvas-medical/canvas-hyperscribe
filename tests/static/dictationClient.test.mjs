import { test } from 'node:test';
import assert from 'node:assert/strict';

// --- Browser-global stubs -------------------------------------------------
// dictationClient.js touches WebSocket/btoa only inside methods, so stubbing
// them before importing is enough to exercise it under Node.

class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  constructor(url, protocols) {
    this.url = url;
    this.protocols = protocols;
    this.readyState = FakeWebSocket.OPEN;
    this.sent = [];
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    FakeWebSocket.instances.push(this);
  }

  send(data) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }

  // Test drivers — invoke the handlers the client attached.
  fireOpen() {
    if (this.onopen) this.onopen();
  }

  fireMessage(obj) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(obj) });
  }

  fireClose(code, reason) {
    this.readyState = FakeWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code, reason });
  }
}
FakeWebSocket.instances = [];

globalThis.WebSocket = FakeWebSocket;
globalThis.btoa = globalThis.btoa || ((s) => Buffer.from(s, 'binary').toString('base64'));

const { createDictationClient } = await import('../../hyperscribe/scribe/static/dictationClient.js');

// --- Helpers --------------------------------------------------------------

const pcm = (samples) => new Int16Array(samples);
const sentTypes = (ws) => ws.sent.map((raw) => JSON.parse(raw).type);

async function connected() {
  FakeWebSocket.instances = [];
  const client = createDictationClient({
    vendor: 'nabla',
    ws_url: 'wss://test/dictate-ws',
    access_token: 'tok',
    sample_rate: 16000,
    encoding: 'PCM_S16LE',
    dictation_locale: 'ENGLISH_US',
    punctuation_mode: 'EXPLICIT',
  });
  const texts = [];
  client.onDictatedText = (t) => texts.push(t);
  const p = client.connect({ text: '', selection_start: 0, selection_length: 0 });
  const ws = FakeWebSocket.instances[0];
  ws.fireOpen();
  await p;
  return { client, ws, texts };
}

// --- Tests ----------------------------------------------------------------

test('routes DICTATED_TEXT units to onDictatedText verbatim while listening', async () => {
  const { ws, texts } = await connected();
  ws.fireMessage({ type: 'DICTATED_TEXT', text: 'Hello ' });
  ws.fireMessage({ type: 'DICTATED_TEXT', text: 'world.' });
  assert.deepEqual(texts, ['Hello ', 'world.']);
});

test('holds the END frame until every buffered audio chunk is acknowledged', async () => {
  const { client, ws } = await connected();
  client.sendAudio(pcm(1600)); // seq 0
  client.sendAudio(pcm(1600)); // seq 1

  const endP = client.end();
  assert.ok(!sentTypes(ws).includes('END'), 'END sent before any audio drained');

  ws.fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 0 });
  assert.ok(!sentTypes(ws).includes('END'), 'END sent while a chunk was still unacked');

  ws.fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 1 });
  assert.ok(sentTypes(ws).includes('END'), 'END not sent after the buffer fully drained');

  ws.fireClose(1000);
  await endP;
});

test('KOALA-6823: DICTATED_TEXT flushed after END (during the drain) is still delivered', async () => {
  const { client, ws, texts } = await connected();
  client.sendAudio(pcm(1600));

  const endP = client.end();
  ws.fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 0 }); // drains buffer -> END is sent
  assert.ok(sentTypes(ws).includes('END'));

  // The server transcribes the tail and flushes it AFTER END, then closes. On a
  // short dictation this tail is most or all of the text — it must not be dropped.
  ws.fireMessage({ type: 'DICTATED_TEXT', text: 'Patient reports a mild cough.' });
  ws.fireClose(1000);
  await endP;

  assert.deepEqual(texts, ['Patient reports a mild cough.']);
});

test('end() force-closes and resolves within the bounded drain window if the server never closes', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { client, ws } = await connected();

  const endP = client.end(); // buffer empty -> END sent immediately
  assert.ok(sentTypes(ws).includes('END'));

  t.mock.timers.tick(15000); // END_TIMEOUT_MS
  await endP; // resolving proves the bounded wait fired

  assert.equal(ws.readyState, FakeWebSocket.CLOSED);
});
