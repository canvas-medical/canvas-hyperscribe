/**
 * Vendor-abstracted WebSocket client for real-time scribe transcription.
 *
 * Implements Nabla network-resilience best practices:
 * - Local FIFO audio buffer between mic and server
 * - AUDIO_CHUNK_ACK processing for reliable delivery
 * - Backpressure: max 10 seconds of in-flight (sent but unacknowledged) audio
 * - Automatic reconnection with exponential backoff
 * - Proper buffer drain before session end
 *
 * See: https://docs.nabla.com/guides/best-practices/transcription-network-resilience
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

const MAX_RECONNECT_ATTEMPTS = 10;
const END_TIMEOUT_MS = 30000;
// If we have in-flight audio and the server hasn't responded in this long,
// consider the connection dead. Browser offline events and WebSocket close
// detection are unreliable on macOS — this catches it at the application level.
const STALE_CONNECTION_MS = 5000;
const HEALTH_CHECK_INTERVAL_MS = 2000;

class NablaScribeClient {
  /**
   * @param {object} config
   * @param {string} config.ws_url
   * @param {string} config.access_token
   * @param {number} config.sample_rate
   * @param {string} config.encoding
   * @param {string[]} config.speech_locales
   * @param {string} config.stream_id
   * @param {function(): Promise<object>} [config.refreshConfig] — async callback
   *   that returns a fresh config object (with a new access_token) when the
   *   current token has expired. Called before each reconnect attempt.
   */
  constructor(config) {
    this._config = config;
    this._refreshConfig = config.refreshConfig || null;
    this._ws = null;
    this._nextSeqId = 0;

    // Audio buffer — FIFO queue.
    // Each entry: { seqId, base64, streamId, sampleCount, sent }
    this._buffer = [];
    this._lastAckedSeqId = -1;
    this._inflightSamples = 0;
    this._maxInflightSamples = 10 * (config.sample_rate || 16000);

    // Connection lifecycle.
    this._initialConnect = true;
    this._connectResolve = null;
    this._connectReject = null;
    this._intentionalClose = false;
    this._reconnectAttempts = 0;
    this._reconnectTimer = null;

    // Connection health check.
    this._lastServerMessageTime = 0;
    this._healthCheckInterval = null;

    // End-of-session state.
    this._ending = false;
    this._endSent = false;
    this._endResolve = null;
    this._endTimeout = null;

    /** @type {function(object): void} */
    this.onTranscriptItem = () => {};
    /** @type {function(string, number=): void} */
    this.onError = () => {};
    /** @type {function(): void} */
    this.onEnd = () => {};
    /** @type {function(): void} */
    this.onDisconnect = () => {};
    /** @type {function(): void} */
    this.onReconnect = () => {};
  }

  /**
   * Open initial WebSocket connection with subprotocol auth.
   * @returns {Promise<void>}
   */
  connect() {
    this._initialConnect = true;
    // Use browser offline/online events for instant network-loss detection.
    // WebSocket close can take 30-60s over TCP; these fire immediately.
    this._offlineHandler = () => this._handleOffline();
    this._onlineHandler = () => this._handleOnline();
    window.addEventListener('offline', this._offlineHandler);
    window.addEventListener('online', this._onlineHandler);
    return new Promise((resolve, reject) => {
      this._connectResolve = resolve;
      this._connectReject = reject;
      this._createWebSocket();
    });
  }

  /**
   * Buffer PCM16 audio and flush to the WebSocket when possible.
   * Audio is never dropped — it stays in the local buffer until acknowledged.
   * @param {Int16Array} pcm16Int16Array
   */
  sendAudio(pcm16Int16Array) {
    if (this._ending) return;

    const seqId = this._nextSeqId++;
    this._buffer.push({
      seqId,
      base64: int16ArrayToBase64(pcm16Int16Array),
      streamId: this._config.stream_id,
      sampleCount: pcm16Int16Array.length,
      sent: false,
    });

    this._flush();
  }

  /**
   * Signal end of audio stream. Drains the buffer, sends END, and waits for
   * the server to close the connection (up to 60 s).
   * @returns {Promise<void>}
   */
  async end() {
    if (this._ending) return;
    this._ending = true;

    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }

    this._flush();

    // Nothing left to do — no connection, no buffered data.
    if (!this._ws && this._buffer.length === 0) return;

    // Disconnected with buffered data — reconnect to drain.
    if (!this._ws && this._buffer.length > 0) {
      this._reconnectAttempts = 0;
      this._scheduleReconnect();
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

  /**
   * Force-close without draining the buffer.
   * Use when the user wants to skip remaining audio catch-up.
   */
  forceEnd() {
    this._intentionalClose = true;
    this._ending = true;
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    this._removeEventListeners();
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
  _createWebSocket() {
    const { ws_url, access_token } = this._config;
    let ws;
    try {
      ws = new WebSocket(ws_url, ['transcribe-protocol', `jwt-${access_token}`]);
    } catch {
      this._handleConnectFailure();
      return;
    }

    ws.onopen = () => {
      this._ws = ws;
      this._reconnectAttempts = 0;
      this._lastServerMessageTime = Date.now();
      this._startHealthCheck();
      this._sendConfig();
      this._flush();

      if (this._initialConnect) {
        this._initialConnect = false;
        if (this._connectResolve) {
          this._connectResolve();
          this._connectResolve = null;
          this._connectReject = null;
        }
      } else {
        this.onReconnect();
      }
    };

    ws.onerror = () => {
      // Handled in onclose.
    };

    ws.onmessage = (event) => this._handleMessage(event.data);

    ws.onclose = () => {
      this._stopHealthCheck();
      if (this._ws === ws) this._ws = null;

      if (this._intentionalClose) {
        this._resolveEnd();
        return;
      }

      // Initial connection failed — reject the connect() promise.
      if (this._initialConnect) {
        this._handleConnectFailure();
        return;
      }

      // Unexpected disconnect during an active session — reconnect.
      this.onDisconnect();
      this._markSentAsUnsent();
      this._scheduleReconnect();
    };
  }

  /** @private */
  _handleConnectFailure() {
    this._initialConnect = false;
    this.onError('WebSocket connection error');
    if (this._connectReject) {
      this._connectReject(new Error('WebSocket connection error'));
      this._connectResolve = null;
      this._connectReject = null;
    }
  }

  /** @private — Periodically check for a stale connection. */
  _startHealthCheck() {
    this._stopHealthCheck();
    this._healthCheckInterval = setInterval(() => {
      if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return;
      if (this._inflightSamples === 0) return;
      if (Date.now() - this._lastServerMessageTime > STALE_CONNECTION_MS) {
        this._abortConnection();
      }
    }, HEALTH_CHECK_INTERVAL_MS);
  }

  /** @private */
  _stopHealthCheck() {
    if (this._healthCheckInterval) {
      clearInterval(this._healthCheckInterval);
      this._healthCheckInterval = null;
    }
  }

  /**
   * @private
   * Immediately abandon the current WebSocket without waiting for the TCP
   * close handshake (which can take 30+ seconds on a dead connection).
   * Fires onDisconnect and begins reconnection right away.
   */
  _abortConnection() {
    this._stopHealthCheck();
    if (this._ws) {
      const ws = this._ws;
      this._ws = null;
      ws.onclose = () => {};
      ws.onerror = () => {};
      ws.onmessage = () => {};
      ws.close();
    }
    this.onDisconnect();
    this._markSentAsUnsent();
    this._scheduleReconnect();
  }

  /** @private — Re-queue sent-but-unacknowledged chunks for resend after reconnect. */
  _markSentAsUnsent() {
    for (const chunk of this._buffer) {
      if (chunk.sent) chunk.sent = false;
    }
    this._inflightSamples = 0;
  }

  /** @private — Browser went offline; proactively close the WebSocket. */
  _handleOffline() {
    if (this._initialConnect || this._intentionalClose) return;
    if (this._ws) this._abortConnection();
  }

  /** @private — Browser came back online; reconnect immediately. */
  _handleOnline() {
    if (this._intentionalClose || this._initialConnect) return;
    // Cancel any pending backoff timer and reconnect now.
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (!this._ws) {
      this._reconnectAttempts = 0;
      this._reconnect();
    }
  }

  /**
   * @private
   * Fetch fresh tokens from the backend and reconnect. Called by
   * _scheduleReconnect and _handleOnline so that an expired JWT is
   * replaced before the new WebSocket handshake.
   */
  async _reconnect() {
    if (this._refreshConfig) {
      try {
        const freshConfig = await this._refreshConfig();
        if (freshConfig && freshConfig.access_token) {
          this._config.access_token = freshConfig.access_token;
        }
      } catch {
        // Fall through with existing token — the connect attempt will fail
        // and trigger another retry via the normal backoff path.
      }
    }
    this._createWebSocket();
  }

  /** @private */
  _scheduleReconnect() {
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.onError('Lost connection to transcription service');
      this._resolveEnd();
      return;
    }
    // Don't waste reconnect attempts while the browser reports offline.
    // _handleOnline will kick off reconnection when network returns.
    if (typeof navigator !== 'undefined' && !navigator.onLine) return;
    const delay = Math.min(1000 * Math.pow(2, this._reconnectAttempts), 30000);
    this._reconnectAttempts++;
    this._reconnectTimer = setTimeout(() => this._reconnect(), delay);
  }

  /**
   * @private
   * Send queued chunks up to the backpressure limit. When ending and the
   * buffer is fully acknowledged, send the END frame.
   */
  _flush() {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return;
    if (this._endSent) return;

    for (const chunk of this._buffer) {
      if (chunk.sent) continue;
      if (this._inflightSamples + chunk.sampleCount > this._maxInflightSamples) break;

      this._ws.send(JSON.stringify({
        type: 'AUDIO_CHUNK',
        payload: chunk.base64,
        stream_id: chunk.streamId,
        seq_id: chunk.seqId,
      }));
      chunk.sent = true;
      this._inflightSamples += chunk.sampleCount;
    }

    // All buffered audio acknowledged — safe to end.
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

    this._lastServerMessageTime = Date.now();

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
      case 'AUDIO_CHUNK_ACK':
        this._handleAck(msg);
        break;
      case 'END':
        this._intentionalClose = true;
        // Server will close the connection after this.
        break;
      case 'ERROR':
      case 'ERROR_MESSAGE':
        this.onError(msg.message || 'Unknown error', msg.code);
        break;
    }
  }

  /**
   * @private
   * Process an acknowledgment: discard acknowledged chunks from the buffer
   * and flush more data now that backpressure headroom has opened up.
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
  _removeEventListeners() {
    if (this._offlineHandler) {
      window.removeEventListener('offline', this._offlineHandler);
      this._offlineHandler = null;
    }
    if (this._onlineHandler) {
      window.removeEventListener('online', this._onlineHandler);
      this._onlineHandler = null;
    }
  }

  /** @private */
  _resolveEnd() {
    if (this._endTimeout) {
      clearTimeout(this._endTimeout);
      this._endTimeout = null;
    }
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    this._stopHealthCheck();
    this._removeEventListeners();
    const resolve = this._endResolve;
    this._endResolve = null;
    this.onEnd();
    if (resolve) resolve();
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
