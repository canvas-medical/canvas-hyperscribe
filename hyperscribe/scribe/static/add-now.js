// Add Now list updates.
//
// Add Now is async: generation can finish while the request is in flight and
// rebuild the lists (generated commands first, provider-added cards after
// them; recommendations replaced outright). Matching the clicked card by its
// position then marks whichever card moved into that slot. Instead, the
// clicked card gets a one-off id when the spinner starts, and every later
// update matches on that id. If the card is gone, nothing is marked.

// Stamp the clicked card with `id`. The clicked card is the `command` object
// itself; `index` is only a fallback if that object is no longer in the list.
export function stampAddNow(list, command, index, id) {
  const target = list.includes(command) ? list.indexOf(command) : index;
  return list.map((item, i) => (i === target ? { ...item, _addNowId: id, _adding: true } : item));
}

// Apply `fn` to the card stamped with `id`, wherever it is now.
export function updateAddNow(list, id, fn) {
  return list.map(item => (item._addNowId === id ? fn(item) : item));
}
