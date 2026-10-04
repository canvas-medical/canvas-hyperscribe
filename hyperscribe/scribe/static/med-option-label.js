// Text for a medication <option>: the drug name, then its current directions, so a
// patient carrying the same drug twice with different sigs has two distinguishable
// entries. Shared by the refill/adjust picker (order-row.js) and the stop medication
// picker (soap-group.js) so the two cannot drift apart.
//
// A native <option> cannot wrap, so a long sig is cut back to the last whole word
// rather than stretching the list past the panel edge. The stopped-medication card
// renders the sig unabridged instead of calling this.
// Zero imports on purpose (same as bmi.js): the test runs it under bare node.
export const SIG_LABEL_MAX_LENGTH = 60;

export function medicationOptionLabel(name, sig, maxLength = SIG_LABEL_MAX_LENGTH) {
  const drug = String(name ?? '').trim();
  const directions = String(sig ?? '').trim().replace(/\s+/g, ' ');
  if (!directions) return drug;
  let shortened = directions;
  if (directions.length > maxLength) {
    const cut = directions.slice(0, maxLength);
    const lastSpace = cut.lastIndexOf(' ');
    shortened = `${(lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd()}...`;
  }
  return drug ? `${drug} - ${shortened}` : shortened;
}
