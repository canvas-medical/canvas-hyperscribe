/**
 * Vendor-abstracted WebSocket client for real-time single-field DICTATION.
 *
 * This is deliberately SEPARATE from scribeClient.js (ambient transcription):
 * dictation talks into one note field post-generation and must never feed the
 * note-generation transcript. It targets Nabla's `dictate-ws` endpoint, which
 * differs from `transcribe-ws`:
 *  - a single `dictation_locale` (not a `speech_locales` array), no `stream_id`
 *  - `punctuation_mode: "EXPLICIT"` — the provider dictates punctuation aloud
 *  - a `text_field_context` (current field text + caret) so dictated words are
 *    inserted at the caret (caret at end ⇒ append, first word capitalised)
 *  - the server replies with append-only DICTATED_TEXT units (immutable, in
 *    order, no partial/final revision) that the client appends verbatim
 *
 * See: https://docs.nabla.com/server/dictate-ws
 */

/**
 * Convert Int16Array to base64 string.
 * @param {Int16Array} int16Array
 * @returns {string}
 */
function int16ArrayToBase64(int16Array) {
  const bytes = new Uint8Array(int16Array.buffer, int16Array.byteOffset, int16Array.byteLength);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

// Fallback drain window after END before we force-close (dictation sessions are
// short, so a generous but bounded wait is enough for the server to flush).
const END_TIMEOUT_MS = 15000;

class NablaDictationClient {
  /**
   * @param {object} config — from the /dictation-config endpoint
   * @param {string} config.ws_url
   * @param {string} config.access_token
   * @param {number} config.sample_rate
   * @param {string} config.encoding
   * @param {string} config.dictation_locale
   * @param {string} config.punctuation_mode
   */
  constructor(config) {
    this._config = config;
    this._ws = null;
    this._textFieldContext = null;

    // Audio buffer — FIFO queue. Each entry: { seqId, base64, sampleCount, sent }.
    // dictate-ws acks audio chunks and errors past ~10s of un-acked audio, so we
    // cap in-flight (sent-but-unacked) audio at ~9s and drain as ACKs arrive.
    this._buffer = [];
    this._nextSeqId = 0;
    this._lastAckedSeqId = -1;
    this._inflightSamples = 0;
    this._maxInflightSamples = 9 * (config.sample_rate || 16000);

    // End-of-session state.
    this._ending = false;
    this._endSent = false;
    this._intentionalClose = false;
    this._ended = false;
    this._endResolve = null;
    this._endTimeout = null;

    /** @type {function(string): void} — one appended DICTATED_TEXT unit */
    this.onDictatedText = () => {};
    /** @type {function(string, number=): void} */
    this.onError = () => {};
    /** @type {function(): void} — fired once the session is fully torn down */
    this.onEnd = () => {};
  }

  /**
   * Open the dictate WebSocket, send CONFIG (with the field's text/caret), and
   * resolve once connected. Rejects if the initial connection fails.
   * @param {object} textFieldContext - has text, selection_start, selection_length
   * @returns {Promise<void>}
   */
  connect(textFieldContext) {
    this._textFieldContext = textFieldContext || { text: '', selection_start: 0, selection_length: 0 };
    return new Promise((resolve, reject) => {
      let opened = false;
      let ws;
      try {
        ws = new WebSocket(this._config.ws_url, ['dictate-protocol', `jwt-${this._config.access_token}`]);
      } catch {
        reject(new Error('WebSocket connection error'));
        return;
      }

      ws.onopen = () => {
        opened = true;
        this._ws = ws;
        this._sendConfig();
        this._flush();
        resolve();
      };

      ws.onerror = () => {
        // Surfaced via onclose.
      };

      ws.onmessage = (event) => this._handleMessage(event.data);

      ws.onclose = () => {
        if (this._ws === ws) this._ws = null;
        if (!opened) {
          reject(new Error('WebSocket connection error'));
          return;
        }
        // Opened, then closed. A clean close after END means the server flushed
        // all dictated text. An unexpected close (e.g. silence timeout 83011)
        // ends the session too — dictation does not auto-reconnect.
        if (!this._intentionalClose && !this._endSent) {
          this.onError('Dictation connection lost');
        }
        this._resolveEnd();
      };
    });
  }

  /**
   * Buffer PCM16 audio and flush to the WebSocket when possible. Safe to call
   * before connect() resolves — audio buffers until the socket opens.
   * @param {Int16Array} pcm16Int16Array
   */
  sendAudio(pcm16Int16Array) {
    if (this._ending) return;
    const seqId = this._nextSeqId++;
    this._buffer.push({
      seqId,
      base64: int16ArrayToBase64(pcm16Int16Array),
      sampleCount: pcm16Int16Array.length,
      sent: false,
    });
    this._flush();
  }

  /**
   * Signal end of dictation: drain the buffer, send END, and wait for the server
   * to flush remaining DICTATED_TEXT and close the socket (up to END_TIMEOUT_MS).
   * @returns {Promise<void>}
   */
  async end() {
    if (this._ending) return;
    this._ending = true;
    this._flush();

    if (!this._ws) {
      this._resolveEnd();
      return;
    }

    return new Promise((resolve) => {
      this._endResolve = resolve;
      this._endTimeout = setTimeout(() => {
        this._intentionalClose = true;
        if (this._ws) {
          this._ws.close();
          this._ws = null;
        }
        this._resolveEnd();
      }, END_TIMEOUT_MS);
    });
  }

  /** Force-close immediately without draining the buffer. */
  forceEnd() {
    this._intentionalClose = true;
    this._ending = true;
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
    this._resolveEnd();
  }

  // ---------------------------------------------------------------------------
  // Internal
  // ---------------------------------------------------------------------------

  /** @private */
  _sendConfig() {
    if (!this._ws) return;
    this._ws.send(JSON.stringify({
      type: 'CONFIG',
      encoding: this._config.encoding,
      sample_rate: this._config.sample_rate,
      dictation_locale: this._config.dictation_locale,
      punctuation_mode: this._config.punctuation_mode,
      text_field_context: this._textFieldContext,
    }));
  }

  /**
   * @private
   * Send queued chunks up to the backpressure limit. When ending and the buffer
   * is fully acknowledged, send the END frame.
   */
  _flush() {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return;
    if (this._endSent) return;

    for (const chunk of this._buffer) {
      if (chunk.sent) continue;
      if (this._inflightSamples + chunk.sampleCount > this._maxInflightSamples) break;

      this._ws.send(JSON.stringify({
        type: 'AUDIO_CHUNK',
        seq_id: chunk.seqId,
        payload: chunk.base64,
      }));
      chunk.sent = true;
      this._inflightSamples += chunk.sampleCount;
    }

    if (this._ending && this._buffer.length === 0 && !this._endSent) {
      this._endSent = true;
      this._ws.send(JSON.stringify({ type: 'END' }));
    }
  }

  /** @private */
  _handleMessage(raw) {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }

    switch (msg.type) {
      case 'DICTATED_TEXT':
        this.onDictatedText(msg.text || '');
        break;
      case 'AUDIO_CHUNK_ACK':
        this._handleAck(msg);
        break;
      case 'ERROR':
      case 'ERROR_MESSAGE':
        this.onError(msg.message || 'Unknown error', msg.code);
        break;
    }
  }

  /**
   * @private
   * Discard acknowledged chunks and flush more now that backpressure has eased.
   */
  _handleAck(msg) {
    const ackId = msg.ack_id;
    if (ackId <= this._lastAckedSeqId) return;
    this._lastAckedSeqId = ackId;

    while (this._buffer.length > 0 && this._buffer[0].seqId <= ackId) {
      const chunk = this._buffer.shift();
      if (chunk.sent) {
        this._inflightSamples -= chunk.sampleCount;
      }
    }

    this._flush();
  }

  /** @private */
  _resolveEnd() {
    if (this._endTimeout) {
      clearTimeout(this._endTimeout);
      this._endTimeout = null;
    }
    const resolve = this._endResolve;
    this._endResolve = null;
    if (!this._ended) {
      this._ended = true;
      this.onEnd();
    }
    if (resolve) resolve();
  }
}

/**
 * Factory for a vendor-specific dictation client.
 * @param {object} config - Config object from /dictation-config
 * @returns {NablaDictationClient}
 */
export function createDictationClient(config) {
  switch (config.vendor) {
    case 'nabla':
      return new NablaDictationClient(config);
    default:
      throw new Error(`Unknown dictation vendor: ${config.vendor}`);
  }
}
