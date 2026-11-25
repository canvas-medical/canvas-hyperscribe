// Name the sections with unsaved edits and take the provider there.
// Open editors carry data-edit-key (the key they report to editingFields), SOAP
// groups carry data-soap-group, and section titles carry data-section-title.

// labels: section titles of the open editors, top to bottom. With none found,
// this is the original message.
export function unsavedEditsMessage(count, labels = []) {
  const noun = count === 1 ? 'edit' : 'edits';
  const names = [...new Set(labels.filter(Boolean))];
  if (names.length === 0) {
    return `${count} unsaved ${noun} — save or cancel to continue.`;
  }
  return `${count} unsaved ${noun}: ${names.join(', ')} — save or cancel to continue.`;
}

// The open editors, top to bottom. Keys are an index (3), an index plus a field
// ("3:code", "3:text" from one diagnosis card) or a placeholder name.
export function findOpenEditors(keys, root = document) {
  const found = new Set();
  for (const key of keys) {
    const el = root.querySelector(`[data-edit-key="${CSS.escape(String(key).split(':')[0])}"]`);
    if (el) found.add(el);
  }
  return [...found].sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
}

// The last section title above `el` in its SOAP group (the group heading if
// none). Page order, because some titles sit beside their rows, not above them.
export function sectionTitleFor(el) {
  const group = el?.closest('[data-soap-group]');
  if (!group) return null;
  let title = null;
  for (const t of group.querySelectorAll('[data-section-title]')) {
    if (t.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) title = t;
  }
  return title?.textContent?.trim() || null;
}

// Scroll to and briefly outline `el`. Some labelled wrappers are styled
// `display: contents` and have no box, so use the nearest ancestor that does.
export function scrollToEditor(el) {
  while (el && getComputedStyle(el).display === 'contents') el = el.parentElement;
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('unsaved-flash');
  setTimeout(() => el.classList.remove('unsaved-flash'), 1600);
}
