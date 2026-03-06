/**
 * Vendor-abstracted WebSocket client for real-time scribe transcription.
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

class NablaScribeClient {
  /**
   * @param {object} config
   * @param {string} config.ws_url
   * @param {string} config.access_token
   * @param {number} config.sample_rate
   * @param {string} config.encoding
   * @param {string[]} config.speech_locales
   * @param {string} config.stream_id
   */
  constructor(config) {
    this._config = config;
    this._ws = null;
    this._seqId = 0;

    /** @type {function(object): void} */
    this.onTranscriptItem = () => {};
    /** @type {function(string): void} */
    this.onError = () => {};
    /** @type {function(): void} */
    this.onEnd = () => {};
  }

  /**
   * Open WebSocket connection with subprotocol auth.
   * @returns {Promise<void>}
   */
  connect() {
    return new Promise((resolve, reject) => {
      const { ws_url, access_token } = this._config;
      this._ws = new WebSocket(ws_url, ['transcribe-protocol', `jwt-${access_token}`]);

      this._ws.onopen = () => {
        this._sendConfig();
        resolve();
      };

      this._ws.onerror = (event) => {
        this.onError('WebSocket connection error');
        reject(new Error('WebSocket connection error'));
      };

      this._ws.onmessage = (event) => {
        this._handleMessage(event.data);
      };

      this._ws.onclose = () => {
        this.onEnd();
      };
    });
  }

  /**
   * Send PCM16 audio data to the WebSocket.
   * @param {Int16Array} pcm16Int16Array
   */
  sendAudio(pcm16Int16Array) {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return;

    this._seqId++;
    const msg = JSON.stringify({
      type: 'AUDIO_CHUNK',
      payload: int16ArrayToBase64(pcm16Int16Array),
      stream_id: this._config.stream_id,
      seq_id: this._seqId,
    });
    this._ws.send(msg);
  }

  /**
   * Signal end of audio stream and wait for the server to flush final
   * transcript items and close the connection.
   * @returns {Promise<void>}
   */
  async end() {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
      this._ws = null;
      return;
    }

    this._ws.send(JSON.stringify({ type: 'END' }));

    // Poll until the server closes the connection (max ~5s).
    for (let i = 0; i < 50; i++) {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        await new Promise((r) => setTimeout(r, 100));
      } else {
        break;
      }
    }

    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
  }

  /** @private */
  _sendConfig() {
    if (!this._ws) return;
    const config = {
      type: 'CONFIG',
      encoding: this._config.encoding,
      sample_rate: this._config.sample_rate,
      speech_locales: this._config.speech_locales,
      streams: [{ id: this._config.stream_id, speaker_type: 'unspecified' }],
      enable_audio_chunk_ack: true,
    };
    this._ws.send(JSON.stringify(config));
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
      case 'TRANSCRIPT_ITEM':
        this.onTranscriptItem({
          item_id: msg.id || '',
          text: msg.text || '',
          speaker: msg.speaker_type || msg.speaker || '',
          start_offset_ms: msg.start_offset_ms || 0,
          end_offset_ms: msg.end_offset_ms || 0,
          is_final: msg.is_final !== false,
        });
        break;
      case 'END':
        this.onEnd();
        break;
      case 'ERROR':
        this.onError(msg.message || 'Unknown error');
        break;
    }
  }
}

/**
 * Factory function to create a vendor-specific scribe client.
 * @param {object} config - Config object from /config endpoint
 * @returns {NablaScribeClient}
 */
export function createScribeClient(config) {
  switch (config.vendor) {
    case 'nabla':
      return new NablaScribeClient(config);
    default:
      throw new Error(`Unknown scribe vendor: ${config.vendor}`);
  }
}
