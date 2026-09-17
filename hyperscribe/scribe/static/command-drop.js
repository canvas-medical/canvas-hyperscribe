// Why a command was left out of the /insert-commands batch — the single source of
// truth for "is this drop the user's choice, or a silent failure we must surface?"
//
// handleInsert splits `commands` into `insertable` and `dropped`. Some drops are
// deliberate (the user unchecked the row, the row is empty, the user dismissed the
// card); one is not (the row failed validation and would be lost without a word).
// Only the last kind may block Approve.
//
// KOALA-6555: this module exists because that distinction used to be hand-written in
// two places — the COMMANDS_FILTERED audit reason and the `droppedForValidation`
// filter — and they drifted. When the ✕ on a condition card started marking
// `data.rejected` instead of deleting the row, a new *intentional* drop reason was
// created; neither copy was taught about it, so dismissing a duplicate condition
// classified as a validation failure and made the note permanently unsignable.
// Both call sites now read from here, so a new drop reason cannot be added to one
// without the other.
//
// Zero imports on purpose (same as bmi.js / questionnaire-score.js): summary.js is
// not importable under Node, so this is the only way the classification can carry
// real unit tests (tests/static/command-drop.test.mjs).

// The two condition-card families. Both render a ✕ that marks `data.rejected` rather
// than deleting the row, so the assessment text survives a mis-click and the card can
// be restored (see renderConditionActions in soap-group.js).
export const CONDITION_COMMAND_TYPES = new Set(['assess', 'diagnose']);

// True when the provider dismissed a condition card with the ✕. Deliberately scoped to
// the condition families rather than testing `data.rejected` on any type: suppressing a
// validation error is only sound for a type that ALSO has a matching "rejected ⇒ not
// insertable" gate. A type that starts writing `data.rejected` without one would
// otherwise inherit silent error suppression and its command would be dropped from the
// batch with no message — the exact failure mode `droppedForValidation` exists to catch.
export const isDismissedCondition = (c) =>
  CONDITION_COMMAND_TYPES.has(c?.command_type) && !!(c?.data && c.data.rejected);

// Classify a dropped command. `empty_display` / `deselected` / `dismissed` are the
// user's choices; `validation` means the row would be silently lost and Approve must
// halt so the provider can fix it.
//
// Order matters and mirrors the precedence the audit log has always used: an empty row
// reports `empty_display` even if it is also deselected or dismissed.
export const dropReason = (c) => {
  if (!c?.display) return 'empty_display';
  if (c.selected === false) return 'deselected';
  if (isDismissedCondition(c)) return 'dismissed';
  return 'validation';
};

// The gate for "should this drop block Approve?" — everything except `validation` is a
// choice the user made on purpose.
export const isIntentionalDrop = (c) => dropReason(c) !== 'validation';
