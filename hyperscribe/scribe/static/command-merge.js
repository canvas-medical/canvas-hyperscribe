// Pure command-merging helpers for the generate flow. Kept free of preact so it can be
// unit-tested under `node --test`, the same reason questionnaire-score.js and
// questionnaire-fill.js are separate from the components that use them.

// Section keys whose cards are provider-added rather than generated, so generation must
// never drop them.
export const AD_HOC_SECTION_KEYS = new Set([
  '_ad_hoc',
  '_objective_ad_hoc',
  '_history_ad_hoc',
  '_subjective_ad_hoc',
  '_charges_ad_hoc',
]);

// Fold a freshly generated command list into whatever is already on the note.
//
// `existing` MUST be the live state at the moment the response lands, not a value
// captured when the request was sent. The automatic questionnaire fill runs in parallel
// with generation and merges its drafted answers into these same commands; on a real
// transcript the fill finished in ~38s while generation was still running, so reading a
// pre-request snapshot here silently erased every drafted answer a few seconds after it
// arrived. Nothing errored, which is what made it hard to spot.
export function mergeGeneratedCommands(existing, generated) {
  const previous = existing || [];
  const fresh = generated || [];
  const generatedTypes = new Set(fresh.map(c => c.command_type));

  // Provider-added cards always survive, whatever generation returned.
  const adHoc = previous.filter(c => AD_HOC_SECTION_KEYS.has(c.section_key));

  // Template-inserted cards survive only where generation did not produce that command
  // type itself, otherwise the two would both render.
  const templateKeep = previous.filter(c =>
    c._template_inserted
    && !AD_HOC_SECTION_KEYS.has(c.section_key)
    && !generatedTypes.has(c.command_type)
  );

  return [...fresh, ...adHoc, ...templateKeep];
}
