// Footer "N unsaved edits" helpers.
//
// The page carries three data attributes for this feature, so nothing here
// depends on CSS class names:
//   data-edit-key       on each row's open editor, set to the same key the row
//                       reports to editingFields through onEditingChange
//   data-soap-group     on each SOAP group container (SUBJECTIVE, ...)
//   data-section-title  on each section title, and on each group heading

// editingFields keys are a command index (3), an index plus a field
// ("3:code" from diagnose-row), or a placeholder name
// ("physical_exam_placeholder"). Rows tag their editor with the part before
// the colon.
export function editKeyBase(key) {
  return String(key).split(':')[0];
}

// labels: section titles of the open editors. Null entries (title not found)
// still count towards `count`; duplicates are shown once.
export function unsavedEditsMessage(count, labels = []) {
  const noun = count === 1 ? 'edit' : 'edits';
  const names = [...new Set(labels.filter(Boolean))];
  if (names.length === 0) {
    return `${count} unsaved ${noun} \u2014 save or cancel to continue.`;
  }
  return `${count} unsaved ${noun}: ${names.join(', ')} \u2014 save or cancel to continue.`;
}

export function findEditRow(key, root = document) {
  const base = editKeyBase(key).replace(/["\\]/g, '\\$&');
  return root.querySelector(`[data-edit-key="${base}"]`);
}

// The title shown above an element: the last data-section-title before it in
// its SOAP group. The group heading comes first in the group, so it is the
// answer when no section title precedes the element. Uses page order because
// some sections render the title as a sibling of the rows, not their parent.
export function sectionTitleFor(el) {
  const group = el?.closest('[data-soap-group]');
  if (!group) return null;
  let title = null;
  for (const t of group.querySelectorAll('[data-section-title]')) {
    if (t.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) title = t;
  }
  return title?.textContent?.trim() || null;
}

export function scrollToEditRow(el) {
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('unsaved-flash');
  setTimeout(() => el.classList.remove('unsaved-flash'), 1600);
}
