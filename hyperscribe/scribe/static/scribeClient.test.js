import { test } from 'node:test';
import assert from 'node:assert/strict';

// --- Browser-global stubs -------------------------------------------------
// scribeClient.js touches WebSocket/window/navigator only inside methods, so
// stubbing them here (before instantiating) is enough to run it under Node.

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
globalThis.window = { addEventListener() {}, removeEventListener() {} };
// Node defines navigator as a non-writable getter; redefine it so the client
// sees navigator.onLine === true (otherwise _scheduleReconnect bails).
Object.defineProperty(globalThis, 'navigator', {
  value: { onLine: true },
  configurable: true,
  writable: true,
});

const { createScribeClient } = await import('./scribeClient.js');

// --- Helpers --------------------------------------------------------------

const pcm = (samples) => new Int16Array(samples);

function makeClient(overrides = {}) {
  FakeWebSocket.instances = [];
  const client = createScribeClient({
    vendor: 'nabla',
    ws_url: 'wss://test/ws',
    access_token: 'tok',
    sample_rate: 16000,
    encoding: 'PCM_S16LE',
    speech_locales: ['ENGLISH_US'],
    stream_id: 'stream1',
    ...overrides,
  });
  client.connect().catch(() => {}); // creates instances[0]; promise unused
  return { client, sockets: FakeWebSocket.instances };
}

function sentSeqIds(ws) {
  return ws.sent
    .map((raw) => JSON.parse(raw))
    .filter((m) => m.type === 'AUDIO_CHUNK')
    .map((m) => m.seq_id);
}

// --- Tests ----------------------------------------------------------------

test('resends only unacknowledged chunks after a reconnect', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600)); // seq 0
  client.sendAudio(pcm(1600)); // seq 1
  client.sendAudio(pcm(1600)); // seq 2
  assert.deepEqual(sentSeqIds(sockets[0]), [0, 1, 2], 'all chunks sent on first connection');

  // Cumulative ack up to seq 1 discards 0 and 1 from the buffer.
  sockets[0].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 1 });

  sockets[0].fireClose(); // network drop
  t.mock.timers.tick(1000); // backoff timer -> reconnect
  assert.equal(sockets.length, 2, 'reconnect opened a fresh socket');

  sockets[1].fireOpen();
  assert.deepEqual(
    sentSeqIds(sockets[1]),
    [2],
    'only the un-acked chunk is replayed — acked audio must NOT be re-transcribed',
  );
});

test('a fully-acked buffer replays nothing after reconnect', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600)); // seq 0
  sockets[0].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 0 });

  sockets[0].fireClose();
  t.mock.timers.tick(1000);
  sockets[1].fireOpen();
  assert.deepEqual(sentSeqIds(sockets[1]), [], 'nothing left to replay');
});

test('onReconnect reports acknowledged audio in samples', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();
  let stats = null;
  client.onReconnect = (s) => {
    stats = s;
  };

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600)); // seq 0
  client.sendAudio(pcm(1600)); // seq 1
  sockets[0].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 1 }); // 3200 samples acked

  sockets[0].fireClose();
  t.mock.timers.tick(1000);
  sockets[1].fireOpen();

  assert.equal(stats.ackedSamples, 3200, 'reconnect anchor = acked audio duration');
  assert.equal(stats.sampleRate, 16000);
});

test('a stale connection (no server response) aborts and reconnects', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600)); // in-flight audio, never acked

  // STALE_CONNECTION_MS is 5000; health check runs every 2000ms.
  t.mock.timers.tick(6000); // health check detects staleness -> abort
  t.mock.timers.tick(1000); // backoff timer -> reconnect
  assert.equal(sockets.length, 2, 'stale connection triggered a reconnect');
});

test('getPendingAudioMs reports un-acknowledged buffered audio', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600)); // 100ms
  client.sendAudio(pcm(1600)); // 100ms
  client.sendAudio(pcm(1600)); // 100ms
  assert.equal(client.getPendingAudioMs(), 300, 'all three chunks pending');

  sockets[0].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 0 });
  assert.equal(client.getPendingAudioMs(), 200, 'acked audio no longer pending');

  sockets[0].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 2 });
  assert.equal(client.getPendingAudioMs(), 0, 'fully drained');
});

test('reconnect backoff grows when drops happen before any ack (no tight storm)', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { sockets } = makeClient();

  sockets[0].fireOpen(); // initial connect
  sockets[0].fireClose(); // drop before any ack -> schedule reconnect (1s, attempts->1)
  t.mock.timers.tick(1000);
  assert.equal(sockets.length, 2, 'first reconnect after 1s');

  sockets[1].fireOpen(); // opens but still no ack
  sockets[1].fireClose(); // drop again -> backoff must grow to 2s (attempts->2)
  t.mock.timers.tick(1000);
  assert.equal(sockets.length, 2, 'second reconnect must NOT fire at 1s — backoff grew');
  t.mock.timers.tick(1000);
  assert.equal(sockets.length, 3, 'second reconnect fires at 2s');
});

test('an ack resets the reconnect backoff (proven-stable connection)', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();

  sockets[0].fireOpen();
  sockets[0].fireClose(); // attempts->1
  t.mock.timers.tick(1000);
  sockets[1].fireOpen();
  client.sendAudio(pcm(1600));
  sockets[1].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 0 }); // connection proven working
  sockets[1].fireClose(); // backoff should be back to 1s, not 2s
  t.mock.timers.tick(1000);
  assert.equal(sockets.length, 3, 'ack reset the backoff, so reconnect fires at 1s again');
});

test('a server-initiated close after END resolves cleanly without reconnecting', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600));
  const ended = client.end();
  sockets[0].fireMessage({ type: 'AUDIO_CHUNK_ACK', ack_id: 0 }); // buffer empties -> END sent
  assert.ok(
    sockets[0].sent.some((raw) => JSON.parse(raw).type === 'END'),
    'END frame sent once the buffer drained',
  );

  // Nabla closes the socket itself after post-processing — WITHOUT sending an
  // END message frame. This must be treated as the graceful finish, not an
  // unexpected disconnect to reconnect/replay.
  sockets[0].fireClose();
  t.mock.timers.tick(5000); // let any (buggy) reconnect backoff fire
  assert.equal(sockets.length, 1, 'must not reconnect after a graceful END/close');

  await ended; // resolves via the clean close, not the 30s END timeout
});

test('onDisconnect reports the ws close code and a ws-close trigger', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();
  let stats = null;
  client.onDisconnect = (s) => { stats = s; };

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600));
  sockets[0].fireClose(1006, 'abnormal closure');

  assert.equal(stats.trigger, 'ws-close');
  assert.equal(stats.code, 1006);
  assert.equal(stats.reason, 'abnormal closure');
});

test('a stale-timeout abort reports the stale trigger', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();
  let stats = null;
  client.onDisconnect = (s) => { stats = s; };

  sockets[0].fireOpen();
  client.sendAudio(pcm(1600)); // in-flight audio, never acked
  t.mock.timers.tick(6000); // health check trips the stale detector

  assert.equal(stats.trigger, 'stale-timeout');
});

test('caps in-flight audio at ~3 seconds (backpressure well under Nabla 10s limit)', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient(); // sample_rate 16000
  sockets[0].fireOpen();

  // Push 5s of audio (50 x 100ms chunks) with no acks. Backpressure should let
  // only ~3s (30 chunks) go in-flight; the rest stays queued.
  for (let i = 0; i < 50; i++) client.sendAudio(pcm(1600));

  assert.equal(sentSeqIds(sockets[0]).length, 30, '~3s of audio in-flight, remainder queued');
});

test('finalizeNow sends END even while audio is still buffered', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();
  sockets[0].fireOpen();
  for (let i = 0; i < 50; i++) client.sendAudio(pcm(1600)); // more than the window -> some queued, none acked

  client.finalizeNow();

  assert.ok(
    sockets[0].sent.some((raw) => JSON.parse(raw).type === 'END'),
    'END sent so the server finalizes the in-flight window instead of losing it',
  );
});

test('transcript items are forwarded to onTranscriptItem', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const { client, sockets } = makeClient();
  const items = [];
  client.onTranscriptItem = (item) => items.push(item);

  sockets[0].fireOpen();
  sockets[0].fireMessage({
    type: 'TRANSCRIPT_ITEM',
    id: 'x1',
    text: 'hello',
    speaker_type: 'PATIENT',
    start_offset_ms: 100,
    end_offset_ms: 900,
    is_final: true,
  });

  assert.equal(items.length, 1);
  assert.equal(items[0].text, 'hello');
  assert.equal(items[0].speaker, 'PATIENT');
});
