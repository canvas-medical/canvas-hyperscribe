import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

export function RecordPanel({ noteDbid }) {
  const [recording, setRecording] = useState(false);

  return html`
    <div class="scribe-container record-panel">
      <h2>Record</h2>
      <p class="note-info">Note: ${noteDbid}</p>
      <button
        class="record-btn ${recording ? 'recording' : ''}"
        onClick=${() => setRecording(!recording)}
      >
        ${recording ? 'Stop Recording' : 'Start Recording'}
      </button>
    </div>
  `;
}
