// Pure helpers for questionnaire answers drafted from the visit transcript. Kept free of
// preact so it can be unit-tested under `node --test`, the same reason
// questionnaire-score.js is separate from questionnaire-row.js.

import { TYPE_TEXT, TYPE_INTEGER } from './questionnaire-score.js';

// A question is drafted while any of its responses still carries `proposed`. Both the
// provenance and the click-to-reveal affordance key off this, so confirming an answer
// retires them together without separate bookkeeping.
export function isDrafted(question) {
  return (question?.responses || []).some(r => r.proposed);
}

export function countDrafted(questions) {
  return (questions || []).filter(isDrafted).length;
}

function hasAnswer(question) {
  const responses = question.responses || [];
  if (question.type === TYPE_TEXT || question.type === TYPE_INTEGER) {
    const val = (responses[0] || {}).value;
    return val !== '' && val !== null && val !== undefined;
  }
  return responses.some(r => r.selected);
}

// Fold a backend fill payload into a questionnaire already on the card.
//
// A question the provider has already answered is left alone. The automatic fill runs in
// parallel with note generation, so a draft can land while the card is open and a
// clinician is typing; their answer wins, always.
export function mergeFilled(current, filled) {
  if (!current || !filled) return current;
  const byDbid = new Map((filled.questions || []).map(q => [q.dbid, q]));
  return {
    ...current,
    is_scored: current.is_scored || !!filled.is_scored,
    scoring_function_name: current.scoring_function_name || filled.scoring_function_name || '',
    questions: (current.questions || []).map(question => {
      const incoming = byDbid.get(question.dbid);
      if (!incoming || !incoming.fill) return question;
      if (hasAnswer(question)) return question;
      const incomingByDbid = new Map((incoming.responses || []).map(r => [r.dbid, r]));
      return {
        ...question,
        fill: incoming.fill,
        responses: (question.responses || []).map((r, idx) => {
          const src = incomingByDbid.get(r.dbid) || (incoming.responses || [])[idx];
          if (!src || !src.selected) return r;
          return { ...r, value: src.value, selected: true, proposed: true };
        }),
      };
    }),
  };
}

// Drop every drafted answer, leaving anything the provider set themselves untouched.
export function clearDrafted(questions) {
  return (questions || []).map(question => {
    if (!isDrafted(question)) return question;
    const blank = question.type === TYPE_TEXT || question.type === TYPE_INTEGER;
    return {
      ...question,
      fill: null,
      responses: (question.responses || []).map(r => ({
        ...r,
        selected: false,
        proposed: false,
        comment: null,
        value: blank ? '' : r.value,
      })),
    };
  });
}
