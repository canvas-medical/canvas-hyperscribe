import { h, Fragment } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;
const ICON_MIC = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`;
const ICON_STOP = html`<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`;

const DATA_FIELD = {
  rfv: 'comment',
  hpi: 'narrative',
  plan: 'narrative',
  lab_results: 'narrative',
  imaging_results: 'narrative',
};

// Fields a provider can dictate into (talk-to-fill, post-generation). Kept
// narrower than DATA_FIELD on purpose: lab/imaging narratives are not dictation
// targets. KOALA-6233.
const DICTATABLE = new Set(['rfv', 'hpi', 'plan']);
// Some sections are plan-typed narratives but not free-text prose targets — the
// Appointments section is a follow-up list, so no dictation mic there. Scoped by
// section_key (not command_type, which is 'plan' for these too).
const NON_DICTATABLE_SECTIONS = new Set(['appointments']);

export function CommandRow({ command, commandIndex, onEdit, onDelete, readOnly, onEditingChange, dictation }) {
  const field = DATA_FIELD[command.command_type];
  // Dictatable narratives (CC / HPI / Plan) start in READ mode even when freshly
  // added and empty, so the dictation mic + "Tap to enter text" both show. Other
  // ad-hoc rows keep auto-opening their editor. KOALA-6233.
  const isNew = onDelete && !command.display && !DICTATABLE.has(command.command_type);
  const [editing, setEditing] = useState(isNew);
  // Dictation (KOALA-6233): a mic on the read view of CC / HPI / Plan streams
  // spoken text straight into the field. Only offered when the parent says it's
  // available (author, editable, not mid-ambient-recording). Kept out of the
  // edit view so live dictation never fights the textarea's local draft.
  const canDictate = Boolean(
    dictation && dictation.available
    && DICTATABLE.has(command.command_type)
    && !NON_DICTATABLE_SECTIONS.has(command.section_key),
  );
  const dictating = canDictate && dictation.activeField === commandIndex;
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [value, setValue] = useState(field ? (command.data[field] || '') : '');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus({ preventScroll: true });
    }
  }, [editing]);

  const handleSave = () => {
    onEdit(commandIndex, { ...command.data, [field]: value });
    setEditing(false);
  };

  const handleCancel = () => {
    if (isNew) {
      onDelete(commandIndex);
      return;
    }
    setValue(field ? (command.data[field] || '') : '');
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (editing && !readOnly) {
    return html`
      <div class="command-row editing">
        <textarea
          ref=${textareaRef}
          class="command-row-textarea"
          rows=${command.command_type === 'hpi' ? 10 : undefined}
          value=${value}
          onInput=${(e) => setValue(e.target.value)}
          onKeyDown=${handleKeyDown}
        />
        <div class="command-row-actions">
          <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
          <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
        </div>
      </div>
    `;
  }

  // Dictation status shown as a small line BELOW the field so it's visible whether
  // or not the field already has text (the placeholder only shows when empty).
  const dictationMsg = !dictating
    ? null
    : dictation.silent
      ? 'No audio detected — check your microphone'
      : dictation.status === 'connecting'
        ? 'Connecting…'
        : 'Listening…';

  return html`
    <${Fragment}>
      <div
        class="command-row${dictating ? ' dictating' : ''}"
        onClick=${() => !readOnly && !dictating && setEditing(true)}
      >
        ${command.display
          ? html`<span class="command-row-text">${command.display}</span>`
          : !readOnly && html`<span class="command-row-placeholder">Tap to enter text</span>`
        }
        ${canDictate && html`
          <button
            type="button"
            class="command-row-mic${dictating ? ' recording' : ''}${dictating && dictation.silent ? ' silent' : ''}${dictation.error && dictating ? ' error' : ''}"
            title=${dictating ? (dictation.silent ? 'No audio detected — check your microphone' : 'Stop dictation') : (dictation.micBlocked ? 'Microphone blocked — allow mic access' : 'Dictate into this field')}
            aria-label=${dictating ? 'Stop dictation' : 'Dictate into this field'}
            aria-pressed=${dictating}
            onClick=${(e) => { e.stopPropagation(); dictation.onToggle(commandIndex); }}
          >${dictating ? ICON_STOP : ICON_MIC}</button>
        `}
      </div>
      ${dictationMsg && html`<div class="command-row-dictation-status${dictation.silent ? ' warning' : ''}">${dictationMsg}</div>`}
    </${Fragment}>
  `;
}
