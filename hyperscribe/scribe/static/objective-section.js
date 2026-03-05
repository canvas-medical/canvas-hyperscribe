import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { Section } from '/plugin-io/api/hyperscribe/scribe/static/section.js';

const html = htm.bind(h);

export function ObjectiveSection({ items }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(items.join('\n'));

  const onSave = () => setEditing(false);

  const lines = value.split('\n').filter(Boolean);

  return html`
    <${Section}
      title="OBJECTIVE"
      editing=${editing}
      onEdit=${() => setEditing(true)}
      onSave=${onSave}
    >
      ${editing
        ? html`<textarea
            class="section-textarea"
            value=${value}
            onInput=${(e) => setValue(e.target.value)}
          />`
        : html`<ul class="section-list">
            ${lines.map(item => html`<li key=${item}>${item}</li>`)}
          </ul>`}
    <//>
  `;
}
