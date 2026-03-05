/**
 * AudioWorklet processor that converts float32 audio samples to PCM16 Int16Array.
 * Batches ~96ms of audio (128 samples/quantum x 24 quanta = 3072 samples at 16kHz)
 * before posting to the main thread.
 */

const BATCH_QUANTA = 24; // 128 * 24 = 3072 samples ≈ 192ms at 16kHz

class RawPcm16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._quantaCount = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channelData = input[0];
    if (!channelData || channelData.length === 0) return true;

    this._buffer.push(new Float32Array(channelData));
    this._quantaCount++;

    if (this._quantaCount >= BATCH_QUANTA) {
      this._flush();
    }

    return true;
  }

  _flush() {
    const totalLength = this._buffer.reduce((sum, chunk) => sum + chunk.length, 0);
    const pcm16 = new Int16Array(totalLength);
    let offset = 0;
    for (const chunk of this._buffer) {
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        pcm16[offset++] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
    }
    this.port.postMessage(pcm16);
    this._buffer = [];
    this._quantaCount = 0;
  }
}

registerProcessor('raw-pcm16-processor', RawPcm16Processor);
