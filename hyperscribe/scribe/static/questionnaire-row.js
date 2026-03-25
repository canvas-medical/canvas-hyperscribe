import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

// ResponseOption type constants (from Canvas SDK).
const TYPE_TEXT = 'TXT';
const TYPE_INTEGER = 'INT';
const TYPE_RADIO = 'SING';
const TYPE_CHECKBOX = 'MULT';

function QuestionnaireSearch({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const timer = useRef(null);

  const doSearch = useCallback(async (q) => {
    setSearching(true);
    try {
      const url = q ? `${API_BASE}/search-questionnaires?query=${encodeURIComponent(q)}` : `${API_BASE}/search-questionnaires?query=`;
      const res = await fetch(url);
      const json = await res.json();
      setResults(json.results || []);
    } catch (err) {
      console.error('Questionnaire search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
      setSearched(true);
    }
  }, []);

  const handleFocus = () => {
    if (!searched) doSearch(query);
  };

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => doSearch(val), DEBOUNCE_MS);
  };

  const handleSelect = (r) => {
    setQuery('');
    setResults([]);
    setSearched(false);
    onSelect(r);
  };

  return html`
    <div style="position: relative;">
      <input
        type="text"
        class="questionnaire-search-input"
        value=${query}
        onInput=${handleInput}
        onFocus=${handleFocus}
        placeholder="Search questionnaires..."
        autoFocus
      />
      ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
      ${results.length > 0 && html`
        <div class="questionnaire-search-dropdown">
          ${results.map(r => html`
            <div
              key=${r.dbid}
              class="questionnaire-search-result"
              onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
            >${r.name}</div>
          `)}
        </div>
      `}
      ${!searching && searched && results.length === 0 && query.length >= 2 && html`
        <div class="questionnaire-search-dropdown">
          <div class="questionnaire-search-result search-no-results">No questionnaires found</div>
        </div>
      `}
    </div>
  `;
}

function QuestionnaireForm({ command, commandIndex, onEdit, onDelete, onCancel }) {
  const [loading, setLoading] = useState(false);
  const [questionnaire, setQuestionnaire] = useState(
    command.data.questionnaire_dbid
      ? { dbid: command.data.questionnaire_dbid, name: command.data.questionnaire_name, questions: command.data.questions || [] }
      : null
  );

  const handleSelectQuestionnaire = useCallback(async (result) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/questionnaire-details?dbid=${result.dbid}`);
      const json = await res.json();
      if (json.error) {
        console.error('Failed to load questionnaire:', json.error);
        return;
      }
      const questions = (json.questions || []).map(q => ({
        dbid: q.dbid,
        label: q.label,
        type: q.type,
        responses: q.options.map(o => ({
          dbid: o.dbid,
          value: (q.type === TYPE_TEXT || q.type === TYPE_INTEGER) ? '' : o.value,
          selected: false,
          comment: null,
        })),
      }));
      setQuestionnaire({ dbid: json.questionnaire_dbid, name: json.questionnaire_name, questions });
    } catch (err) {
      console.error('Failed to load questionnaire details:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleResponseChange = (qIdx, rIdx, field, value) => {
    setQuestionnaire(prev => {
      const questions = prev.questions.map((q, qi) => {
        if (qi !== qIdx) return q;
        const responses = q.responses.map((r, ri) => {
          if (field === 'selected' && q.type === TYPE_RADIO) {
            return { ...r, selected: ri === rIdx };
          }
          if (ri !== rIdx) return r;
          return { ...r, [field]: value };
        });
        return { ...q, responses };
      });
      return { ...prev, questions };
    });
  };

  const handleTextChange = (qIdx, value) => {
    setQuestionnaire(prev => {
      const questions = prev.questions.map((q, qi) => {
        if (qi !== qIdx) return q;
        const responses = q.responses.map((r, ri) => ri === 0 ? { ...r, value } : r);
        return { ...q, responses };
      });
      return { ...prev, questions };
    });
  };

  const handleSave = () => {
    if (!questionnaire) return;
    onEdit(commandIndex, {
      questionnaire_dbid: questionnaire.dbid,
      questionnaire_name: questionnaire.name,
      questions: questionnaire.questions,
    }, 'questionnaire');
  };

  if (!questionnaire) {
    return html`
      <div>
        ${loading
          ? html`<span class="diag-search-spinner">Loading questionnaire...</span>`
          : html`<${QuestionnaireSearch} onSelect=${handleSelectQuestionnaire} />`
        }
      </div>
    `;
  }

  return html`
    <div>
      <div class="questionnaire-header">${questionnaire.name}</div>
      ${questionnaire.questions.map((q, qIdx) => html`
        <div class="questionnaire-question" key=${q.dbid}>
          <div class="questionnaire-question-label">${q.label}</div>
          ${q.type === TYPE_RADIO && html`
            <div class="questionnaire-options">
              ${q.responses.map((r, rIdx) => html`
                <label class="questionnaire-option" key=${r.dbid}>
                  <input
                    type="radio"
                    name=${'q-' + commandIndex + '-' + q.dbid}
                    checked=${r.selected}
                    onChange=${() => handleResponseChange(qIdx, rIdx, 'selected', true)}
                  />
                  <span>${r.value}</span>
                </label>
              `)}
            </div>
          `}
          ${q.type === TYPE_CHECKBOX && html`
            <div class="questionnaire-options">
              ${q.responses.map((r, rIdx) => html`
                <div key=${r.dbid}>
                  <label class="questionnaire-option">
                    <input
                      type="checkbox"
                      checked=${r.selected}
                      onChange=${(e) => handleResponseChange(qIdx, rIdx, 'selected', e.target.checked)}
                    />
                    <span>${r.value}</span>
                  </label>
                  ${r.selected && html`
                    <input
                      type="text"
                      class="questionnaire-option-comment"
                      placeholder="Comment (optional)"
                      value=${r.comment || ''}
                      onInput=${(e) => handleResponseChange(qIdx, rIdx, 'comment', e.target.value)}
                    />
                  `}
                </div>
              `)}
            </div>
          `}
          ${q.type === TYPE_TEXT && html`
            <input
              type="text"
              class="questionnaire-text-input"
              value=${(q.responses[0] || {}).value || ''}
              onInput=${(e) => handleTextChange(qIdx, e.target.value)}
              placeholder="Enter response..."
            />
          `}
          ${q.type === TYPE_INTEGER && html`
            <input
              type="number"
              class="questionnaire-text-input"
              style="max-width: 120px;"
              value=${(q.responses[0] || {}).value || ''}
              onInput=${(e) => handleTextChange(qIdx, e.target.value)}
              placeholder="0"
            />
          `}
        </div>
      `)}
      <div class="questionnaire-form-actions">
        <button type="button" class="rec-btn rec-btn-reject" onClick=${onCancel} title="Cancel">${ICON_X}</button>
        <button type="button" class="rec-btn rec-btn-accept" onClick=${handleSave} title="Save">${ICON_CHECK}</button>
      </div>
    </div>
  `;
}

function countAnswered(questions) {
  return questions.filter(q => {
    if (q.type === TYPE_TEXT || q.type === TYPE_INTEGER) {
      const val = (q.responses[0] || {}).value;
      return val !== '' && val !== null && val !== undefined;
    }
    return q.responses.some(r => r.selected);
  }).length;
}

export function QuestionnaireRow({ command, commandIndex, onEdit, onDelete, readOnly }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);

  const handleCancel = () => {
    if (isNew) {
      onDelete(commandIndex);
      return;
    }
    setEditing(false);
  };

  const handleEdit = (index, data, type) => {
    onEdit(index, data, type);
    setEditing(false);
  };

  if (editing) {
    return html`
      <div class="order-row editing" onKeyDown=${(e) => e.key === 'Escape' && handleCancel()}>
        <${QuestionnaireForm}
          command=${command}
          commandIndex=${commandIndex}
          onEdit=${handleEdit}
          onDelete=${onDelete}
          onCancel=${handleCancel}
        />
      </div>
    `;
  }

  const questions = command.data.questions || [];
  const answered = countAnswered(questions);
  const total = questions.length;

  return html`
    <div class="questionnaire-view" onClick=${() => !readOnly && setEditing(true)}>
      <div class="questionnaire-view-content">
        <span class="questionnaire-view-name">${command.display || '(empty)'}</span>
      </div>
      ${total > 0 && html`
        <span class="questionnaire-answered-badge">${answered}/${total} answered</span>
      `}
    </div>
  `;
}
