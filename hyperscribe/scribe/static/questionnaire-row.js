import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

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
      ? {
          dbid: command.data.questionnaire_dbid,
          name: command.data.questionnaire_name,
          is_scored: !!command.data.is_scored,
          scoring_function_name: command.data.scoring_function_name || '',
          questions: command.data.questions || [],
        }
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
          code: o.code || '',
          score_value: o.score_value || '',
          selected: false,
          comment: null,
        })),
      }));
      setQuestionnaire({
        dbid: json.questionnaire_dbid,
        name: json.questionnaire_name,
        is_scored: !!json.is_scored,
        scoring_function_name: json.scoring_function_name || '',
        questions,
      });
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
      is_scored: !!questionnaire.is_scored,
      scoring_function_name: questionnaire.scoring_function_name || '',
      questions: questionnaire.questions,
    }, 'questionnaire');
  };

  if (!questionnaire) {
    return html`
      <div class="questionnaire-form">
        ${loading
          ? html`<span class="diag-search-spinner">Loading questionnaire...</span>`
          : html`<${QuestionnaireSearch} onSelect=${handleSelectQuestionnaire} />`
        }
      </div>
    `;
  }

  return html`
    <div class="questionnaire-form">
      <div class="questionnaire-header">${questionnaire.name}</div>
      <div class="questionnaire-questions-2col">
      ${questionnaire.questions.map((q, qIdx) => html`
        <div class="questionnaire-question" key=${q.dbid}>
          <div class="questionnaire-question-label">
            ${q.label}
            ${q.type === TYPE_CHECKBOX && html`<span class="questionnaire-question-hint"> · Select all that apply</span>`}
          </div>
          ${q.type === TYPE_RADIO && html`
            <div class="questionnaire-chips" role="radiogroup">
              ${q.responses.map((r, rIdx) => html`
                <button
                  type="button"
                  class=${'questionnaire-chip' + (r.selected ? ' selected' : '')}
                  role="radio"
                  aria-checked=${r.selected}
                  key=${r.dbid}
                  onClick=${() => handleResponseChange(qIdx, rIdx, 'selected', true)}
                >${r.value}</button>
              `)}
            </div>
          `}
          ${q.type === TYPE_CHECKBOX && html`
            <div class="questionnaire-chips">
              ${q.responses.map((r, rIdx) => html`
                <button
                  type="button"
                  class=${'questionnaire-chip' + (r.selected ? ' selected' : '')}
                  role="checkbox"
                  aria-checked=${r.selected}
                  key=${r.dbid}
                  onClick=${() => handleResponseChange(qIdx, rIdx, 'selected', !r.selected)}
                >${r.value}</button>
              `)}
            </div>
            ${q.responses.some(r => r.selected) && html`
              <div class="questionnaire-chip-comments">
                ${q.responses.map((r, rIdx) => r.selected && html`
                  <div class="questionnaire-chip-comment-row" key=${r.dbid}>
                    <span class="questionnaire-chip-comment-label">${r.value}</span>
                    <input
                      type="text"
                      class="questionnaire-chip-comment-input"
                      placeholder="Comment (optional)"
                      value=${r.comment || ''}
                      onInput=${(e) => handleResponseChange(qIdx, rIdx, 'comment', e.target.value)}
                    />
                  </div>
                `)}
              </div>
            `}
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
      </div>
      <div class="questionnaire-form-actions">
        <button type="button" class="form-btn form-btn-cancel" onClick=${onCancel}>Cancel</button>
        <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
      </div>
    </div>
  `;
}

function countAnswered(questions) {
  return questions.filter(q => {
    if (q.skipped === true) return true;
    if (q.type === TYPE_TEXT || q.type === TYPE_INTEGER) {
      const val = (q.responses[0] || {}).value;
      return val !== '' && val !== null && val !== undefined;
    }
    return q.responses.some(r => r.selected);
  }).length;
}

// A questionnaire is "complete" when every question is either answered or explicitly skipped.
function isComplete(questions) {
  if (!questions || questions.length === 0) return false;
  return questions.every(q => {
    if (q.skipped === true) return true;
    if (q.type === TYPE_TEXT || q.type === TYPE_INTEGER) {
      const val = (q.responses[0] || {}).value;
      return val !== '' && val !== null && val !== undefined;
    }
    return q.responses.some(r => r.selected);
  });
}

// Additive scoring: sum the numeric score_value of each selected response across radio/checkbox
// questions, plus the integer value of integer questions. Free-text contributes nothing. Skipped
// questions are excluded. Returns null when no numeric data could be parsed (e.g. older saved
// commands that predate the scoring metadata, or unscored questionnaires).
//
// Deliberately does NOT fall back to parsing `code`: LOINC question codes ("44249-1") would
// parseFloat to a non-NaN number and silently masquerade as a clinical score. If a scored
// questionnaire's score_value is missing, surfacing no score is safer than a fabricated one.
function computeScore(questions) {
  if (!questions || questions.length === 0) return null;
  let sum = 0;
  let any = false;
  for (const q of questions) {
    if (q.skipped === true) continue;
    if (q.type === TYPE_TEXT) continue;
    if (q.type === TYPE_INTEGER) {
      const v = (q.responses[0] || {}).value;
      const n = parseFloat(v);
      if (!Number.isNaN(n)) { sum += n; any = true; }
      continue;
    }
    for (const r of q.responses) {
      if (!r.selected) continue;
      const n = parseFloat(r.score_value);
      if (!Number.isNaN(n)) { sum += n; any = true; }
    }
  }
  return any ? sum : null;
}

// Render the response for a single question in the read-only expanded list.
// Returns null when the question is unanswered (caller decides how to display).
function renderResponse(q) {
  if (q.skipped === true) {
    return html`<span class="questionnaire-readonly-skipped">Skipped</span>`;
  }
  if (q.type === TYPE_TEXT) {
    const val = (q.responses[0] || {}).value;
    if (val === '' || val === null || val === undefined) return null;
    return html`<span class="questionnaire-readonly-answer">${val}</span>`;
  }
  if (q.type === TYPE_INTEGER) {
    const val = (q.responses[0] || {}).value;
    if (val === '' || val === null || val === undefined) return null;
    return html`<span class="questionnaire-readonly-answer">${val}</span>`;
  }
  const selected = q.responses.filter(r => r.selected);
  if (selected.length === 0) return null;
  // Comma-separated for both radio (always one) and checkbox; checkbox comments render inline as "Value (comment)".
  const parts = selected.map(r => {
    const comment = (r.comment || '').trim();
    return comment ? `${r.value} (${comment})` : r.value;
  });
  return html`<span class="questionnaire-readonly-answer">${parts.join(', ')}</span>`;
}

export function QuestionnaireRow({ command, commandIndex, onEdit, onDelete, readOnly, onEditingChange }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);

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

  if (editing && !readOnly) {
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
  const complete = isComplete(questions);
  const isScored = !!command.data.is_scored;
  const score = isScored && complete ? computeScore(questions) : null;
  // Pre-approval (editable) cards surface incompleteness with an amber pill so a clinician doesn't miss
  // something before signing off. Post-approval (readOnly) cards stay quiet — the score badge alone speaks.
  const statusBadge = !readOnly && total > 0 && !complete
    ? (answered === 0
        ? html`<span class="questionnaire-status-badge warning">Not started</span>`
        : html`<span class="questionnaire-status-badge">${answered}/${total} answered</span>`)
    : null;
  const showResponses = readOnly && total > 0;

  return html`
    <div class="questionnaire-view-wrap">
      <div
        class=${'questionnaire-view' + (readOnly ? ' readonly' : '')}
        onClick=${readOnly ? null : () => setEditing(true)}
      >
        <div class="questionnaire-view-content">
          <span class="questionnaire-view-name">${command.display || '(empty)'}</span>
        </div>
        ${statusBadge}
        ${score !== null && html`
          <span class="questionnaire-score-badge">Score: ${score}</span>
        `}
      </div>
      ${showResponses && html`
        <dl class="questionnaire-readonly-list">
          ${questions.map(q => {
            const answer = renderResponse(q);
            return html`
              <div class="questionnaire-readonly-row" key=${q.dbid}>
                <dt class="questionnaire-readonly-label">${q.label}</dt>
                <dd class="questionnaire-readonly-value">
                  ${answer || html`<span class="questionnaire-readonly-empty">—</span>`}
                </dd>
              </div>
            `;
          })}
        </dl>
      `}
    </div>
  `;
}
