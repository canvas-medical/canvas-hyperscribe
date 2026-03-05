import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

/**
 * Reusable section wrapper with a header, edit/save toggle, and body slot.
 *
 * Props:
 *   title    — section heading (e.g. "SUBJECTIVE")
 *   editing  — whether the section is in edit mode
 *   onEdit   — callback to enter edit mode
 *   onSave   — callback to leave edit mode (save)
 *   children — section body content
 */
export function Section({ title, editing, onEdit, onSave, children }) {
  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">${title}</span>
        ${editing
          ? html`<button class="edit-btn" onClick=${onSave}>Save</button>`
          : html`<button class="edit-btn" onClick=${onEdit}>Edit</button>`}
      </div>
      <div class="section-body">
        ${children}
      </div>
    </div>
  `;
}
