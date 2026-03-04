import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { useAutoResize } from '/plugin-io/api/hyperscribe/scribe/static/resize.js';

const html = htm.bind(h);

export function Transcript({ noteDbid }) {
  useAutoResize();

  return html`
    <div class="scribe-container">
      <h2>Transcript</h2>
      <p class="note-info">Note: ${noteDbid}</p>
      <p>Transcript content will appear here.</p>
    </div>
  `;
}
