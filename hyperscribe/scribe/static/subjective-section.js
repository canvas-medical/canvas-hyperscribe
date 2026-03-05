import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { Section } from '/plugin-io/api/hyperscribe/scribe/static/section.js';

const html = htm.bind(h);

export function SubjectiveSection({ text }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(text);

  const onSave = () => setEditing(false);

  return html`
    <${Section}
      title="SUBJECTIVE"
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
        : html`<p class="section-text">${value}</p>`}
    <//>
  `;
}
