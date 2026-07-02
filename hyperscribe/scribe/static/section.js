import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

/**
 * Reusable read-only section wrapper with a header and body slot.
 *
 * Props:
 *   title    — section heading (e.g. "SUBJECTIVE")
 *   children — section body content
 */
export function Section({ title, children }) {
  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">${title}</span>
      </div>
      <div class="section-body">
        ${children}
      </div>
    </div>
  `;
}
