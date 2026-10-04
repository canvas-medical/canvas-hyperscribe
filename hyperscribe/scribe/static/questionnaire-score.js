// Shared questionnaire scoring + completion helpers used by both the
// questionnaire row (to render its own score badge) and the vitals card
// (to mirror completed questionnaire scores alongside BP / HR / BMI).

export const TYPE_TEXT = 'TXT';
export const TYPE_INTEGER = 'INT';
export const TYPE_RADIO = 'SING';
export const TYPE_CHECKBOX = 'MULT';

// A questionnaire is "complete" when every question is either answered or explicitly skipped.
export function isComplete(questions) {
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
export function computeScore(questions) {
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

// Collect [{name, score}] for every questionnaire command in `commands` that is scored,
// complete, and yields a numeric score. Skips unscored or incomplete questionnaires.
// Used by the vitals card to mirror screening scores (PHQ-9, GAD-7, AUDIT-C, …) inline.
export function collectQuestionnaireScores(commands) {
  if (!commands) return [];
  const out = [];
  for (const cmd of commands) {
    if (cmd?.command_type !== 'questionnaire') continue;
    const data = cmd.data || {};
    if (!data.is_scored) continue;
    if (!isComplete(data.questions)) continue;
    const score = computeScore(data.questions);
    if (score == null) continue;
    out.push({ name: data.questionnaire_name || '', score });
  }
  return out;
}
