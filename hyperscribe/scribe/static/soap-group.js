import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

export function SoapGroup({ title, sections }) {
  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">${title}</span>
      </div>
      <div class="section-body">
        ${sections.map(s => html`
          <div class="subsection" key=${s.key}>
            <div class="subsection-title">${s.title}</div>
            <p class="section-text">${s.text}</p>
          </div>
        `)}
      </div>
    </div>
  `;
}
