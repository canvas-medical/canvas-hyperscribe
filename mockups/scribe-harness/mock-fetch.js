/*
 * mock-fetch.js — intercepts every Scribe data call so the real components
 * run with no backend, no LLM, no Canvas.
 *
 * Classic script (no imports) so the patch is installed before any module
 * mounts. EVERY data endpoint in the app sits under a single base:
 *     /plugin-io/api/hyperscribe/scribe-session/<endpoint>
 * so one router covers them all. Anything not explicitly handled falls through
 * to a benign 200 `{}` (logged) — the app degrades gracefully rather than
 * throwing, which keeps the mock honest about what still needs a fixture.
 *
 * Response SHAPES match what each component reads. Searches return
 * `{ results: [...] }`; list endpoints use their own keys (`{ tests }`,
 * `{ conditions }`, `{ medications }`, `{ assignees }`, `{ lab_partners }`,
 * `{ providers }`, `{ labels }`). Getting these wrappers wrong makes the
 * dropdowns silently empty, so they are kept in sync with the row components.
 *
 * Tunables on window.__MOCK:
 *   latencyMs   — simulated round-trip delay (default 250)
 *   failNext    — set to an endpoint name to force the next call to it to 500
 *   log         — console.debug every intercepted call
 *   noteCommands — array returned by /note-commands (set per scenario)
 *   recording    — recording-state override (see mock-recording-hook.js)
 */
(function () {
  'use strict';

  const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
  const realFetch = window.fetch.bind(window);

  window.__MOCK = Object.assign({ latencyMs: 250, failNext: null, log: true }, window.__MOCK);

  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));

  // ── canned search/list data ───────────────────────────────────────────────
  const MEDS = [
    { fdb_code: '451234', medication_name: 'Metformin 500 mg tablet' },
    { fdb_code: '451235', medication_name: 'Metformin 1000 mg tablet' },
    { fdb_code: '209876', medication_name: 'Lisinopril 10 mg tablet' },
    { fdb_code: '209900', medication_name: 'Enalapril 5 mg tablet' },
    { fdb_code: '331122', medication_name: 'Atorvastatin 20 mg tablet' },
  ];
  const DIAGNOSES = [
    { code: 'E11.9', display: 'Type 2 diabetes mellitus without complications', formatted_code: 'E11.9' },
    { code: 'I10', display: 'Essential (primary) hypertension', formatted_code: 'I10' },
    { code: 'E78.5', display: 'Hyperlipidemia, unspecified', formatted_code: 'E78.5' },
    { code: 'J06.9', display: 'Acute upper respiratory infection, unspecified', formatted_code: 'J06.9' },
    { code: 'J45.909', display: 'Unspecified asthma, uncomplicated', formatted_code: 'J45.909' },
  ];
  const CHARGES = [
    { cpt_code: '99213', short_name: 'Office visit, est, low', full_name: 'Office visit, established patient, low complexity', description: 'Office visit, established patient, low complexity' },
    { cpt_code: '99214', short_name: 'Office visit, est, moderate', full_name: 'Office visit, established patient, moderate complexity', description: 'Office visit, established patient, moderate complexity' },
    { cpt_code: '36415', short_name: 'Venipuncture', full_name: 'Routine venipuncture', description: 'Routine venipuncture' },
  ];
  const CONDITIONS = [
    { code: 'E11.9', display: 'Type 2 diabetes mellitus' },
    { code: 'I10', display: 'Essential hypertension' },
    { code: 'J45.909', display: 'Asthma, unspecified' },
  ];
  const PROCEDURES = [
    { code: '44970', display: 'Laparoscopic appendectomy' },
    { code: '47562', display: 'Laparoscopic cholecystectomy' },
    { code: '29881', display: 'Knee arthroscopy with meniscectomy' },
  ];
  const RELATIVES = [
    { code: 'MTH', display: 'Mother' }, { code: 'FTH', display: 'Father' },
    { code: 'SIS', display: 'Sister' }, { code: 'BRO', display: 'Brother' },
  ];

  const filterByQuery = (url, arr, field) => {
    const q = (new URL(url, location.origin).searchParams.get('query') || '').toLowerCase();
    if (!q) return arr;
    return arr.filter((x) => String(x[field]).toLowerCase().includes(q));
  };

  // ── router: endpoint suffix -> handler. Return value becomes 200 JSON. ──────
  const ROUTES = {
    // recording config (mock-recording-hook never connects, but answer anyway)
    'config': () => ({ vendor: 'nabla', ws_url: 'wss://example.invalid', access_token: 'mock', sample_rate: 16000, encoding: 'pcm16', speech_locales: ['en'], stream_id: 'mock-stream' }),

    // list endpoints (each with its own wrapper key)
    'assignees': () => ({ assignees: [
      { type: 'team', id: 't1', label: 'Care Team' },
      { type: 'staff', id: 's1', label: 'Dr. Alex Reyes' },
      { type: 'staff', id: 's2', label: 'RN Jordan Patel' },
    ] }),
    'templates': () => ({ templates: [{ id: 'tmpl-1', name: 'Annual Physical' }, { id: 'tmpl-2', name: 'Diabetes Follow-up' }] }),
    'visit-templates': () => ({ templates: [{ id: 'tmpl-2', name: 'Diabetes Follow-up', charges: ['99214'] }] }),
    'task-labels': () => ({ labels: ['Urgent', 'Routine', 'Lab follow-up', 'Referral'] }),
    'lab-partners': () => ({ lab_partners: [{ id: 'quest', name: 'Quest Diagnostics' }, { id: 'labcorp', name: 'LabCorp' }] }),
    'ordering-providers': () => ({ providers: [{ id: 's1', label: 'Dr. Alex Reyes' }, { id: 's3', label: 'Dr. Priya Nair' }] }),

    // patient chart lists (removal rows + add-condition)
    'patient-conditions': () => ({ conditions: [
      { condition_id: 'c1', condition_name: 'Acute sinusitis', code: 'J01.90', display: 'Acute sinusitis' },
      { condition_id: 'c2', condition_name: 'Hyperlipidemia', code: 'E78.5', display: 'Hyperlipidemia' },
    ] }),
    'patient-medications': () => ({ medications: [
      { medication_id: 'm1', medication_name: 'Atorvastatin 20 mg' },
      { medication_id: 'm2', medication_name: 'Lisinopril 10 mg' },
    ] }),
    'patient-allergies': () => ({ allergies: [
      { allergy_id: 'a1', allergy_name: 'Sulfa drugs' },
      { allergy_id: 'a2', allergy_name: 'Latex' },
    ] }),
    'patient-medications-for-refill': () => ({ medications: [
      { fdb_code: '451235', medication_name: 'Metformin 1000 mg tablet', sig: 'Take 1 tablet twice daily', days_supply: 90, quantity_to_dispense: 180, refills: 3, substitutions: 'allowed' },
    ] }),

    // searches — all return { results: [...] }
    'search-medications': (url) => ({ results: filterByQuery(url, MEDS, 'medication_name') }),
    'search-diagnoses': (url) => ({ results: filterByQuery(url, DIAGNOSES, 'display') }),
    'search-charges': (url) => ({ results: filterByQuery(url, CHARGES, 'description') }),
    'search-imaging': (url) => ({ results: filterByQuery(url, [
      { value: '71046', display: 'Radiologic exam, chest, 2 views' },
      { value: '70450', display: 'CT head without contrast' },
    ], 'display') }),
    'search-imaging-centers': () => ({ results: [{ data: { id: 'ic1' }, name: 'City Imaging Center', description: 'Radiology · 456 Oak Ave' }] }),
    'search-pharmacies': () => ({ results: [
      { ncpdp: '5555555555', name: 'Walgreens #1234 — Main St', preferred: true },
      { ncpdp: '6666666666', name: 'CVS — Downtown' },
    ] }),
    'search-allergies': (url) => ({ results: filterByQuery(url, [
      { concept_id: '1191', concept_id_type: 'rxnorm', description: 'Penicillin' },
      { concept_id: '1234', concept_id_type: 'rxnorm', description: 'Sulfa drugs' },
      { concept_id: '5640', concept_id_type: 'rxnorm', description: 'Ibuprofen' },
    ], 'description') }),
    'search-questionnaires': (url) => ({ results: filterByQuery(url, [
      { dbid: 42, name: 'PHQ-9' }, { dbid: 43, name: 'GAD-7' }, { dbid: 44, name: 'Social History' },
    ], 'name') }),
    'search-refer-providers': () => ({ results: [{ data: { id: 'sp1' }, name: 'Dr. Jane Smith, Cardiology', description: 'Cardiology · 123 Main St' }] }),
    'search-medical-history': (url) => ({ results: filterByQuery(url, CONDITIONS, 'display') }),
    'search-surgical-history': (url) => ({ results: filterByQuery(url, PROCEDURES, 'display') }),
    'search-family-history': (url) => ({ results: filterByQuery(url, CONDITIONS, 'display') }),
    'search-family-relation': (url) => ({ results: filterByQuery(url, RELATIVES, 'display') }),

    // lab tests for a partner — { tests: [...] }
    'lab-partner-tests': () => ({ tests: [
      { order_code: '496', order_name: 'Hemoglobin A1c' },
      { order_code: '7600', order_name: 'Lipid Panel' },
      { order_code: '899', order_name: 'TSH' },
    ] }),

    // drug-drug / drug-allergy interactions (none, by default)
    'check-interactions': () => ({ drug_interactions: [], allergy_interactions: [] }),

    // full questionnaire detail loaded when one is selected
    'questionnaire-details': () => ({
      questionnaire_dbid: 42, questionnaire_name: 'PHQ-9', is_scored: true, scoring_function_name: 'phq9',
      questions: [
        { dbid: 101, label: 'Little interest or pleasure in doing things?', type: 'SING', responses: [
          { dbid: 1, value: 'Not at all', code: 'LA6568-5', score_value: '0', selected: false },
          { dbid: 2, value: 'Several days', code: 'LA6569-3', score_value: '1', selected: false },
          { dbid: 3, value: 'More than half the days', code: 'LA6570-1', score_value: '2', selected: false },
          { dbid: 4, value: 'Nearly every day', code: 'LA6571-9', score_value: '3', selected: false },
        ] },
        { dbid: 102, label: 'Feeling down, depressed, or hopeless?', type: 'SING', responses: [
          { dbid: 5, value: 'Not at all', code: 'LA6568-5', score_value: '0', selected: false },
          { dbid: 6, value: 'Several days', code: 'LA6569-3', score_value: '1', selected: false },
          { dbid: 7, value: 'More than half the days', code: 'LA6570-1', score_value: '2', selected: false },
          { dbid: 8, value: 'Nearly every day', code: 'LA6571-9', score_value: '3', selected: false },
        ] },
      ],
    }),

    // GET cache (skipped when initialData present, but answer anyway)
    'summary': () => ({ note: null, commands: [], recommendations: [] }),
    // Commands currently on the note (chart command-rail sync). syncNoteCommands
    // DROPS any local command whose command_uuid isn't echoed here, so scenarios
    // that pre-load already-documented commands (e.g. amending) surface theirs
    // via window.__MOCK.noteCommands.
    'note-commands': () => ({ commands: window.__MOCK.noteCommands || [] }),
    'summary-progress': () => ({ step: -1, total: 0, label: '' }),
    'transcript': () => ({ items: [], finalized: false, started: false }),
    'audit-log': () => ({ events: [] }),
    'debug-cache': () => ({}),

    // POST mutations — acknowledge success
    'save-summary': () => ({ ok: true }),
    'save-transcript': () => ({ ok: true }),
    'save-audit-log': () => ({ ok: true }),
    'insert-commands': () => ({ ok: true, inserted: [] }),
    'insert-metadata': () => ({ ok: true }),
    'edit-existing-commands': () => ({ ok: true }),
    'delete-existing-commands': () => ({ ok: true }),
    'verify-commands': () => ({ ok: true, groups: [] }),
    'enrich-charges': () => ({ ok: true, charges: [] }),
    'carry-forward-background': () => ({ ok: true }),
    'sign-note': () => ({ ok: true }),
    'generate-summary': () => ({ ok: true }),
  };

  function endpointOf(url) {
    const idx = url.indexOf(API_BASE + '/');
    if (idx === -1) return null;
    const rest = url.slice(idx + API_BASE.length + 1);
    return rest.split('?')[0].split('/')[0];
  }

  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (!url.includes(API_BASE)) return realFetch(input, init);

    const endpoint = endpointOf(url);
    if (window.__MOCK.log) console.debug('[mock-fetch]', (init && init.method) || 'GET', endpoint, url);

    await delay(window.__MOCK.latencyMs);

    if (window.__MOCK.failNext && window.__MOCK.failNext === endpoint) {
      window.__MOCK.failNext = null;
      return json({ error: `mock forced failure: ${endpoint}` }, 500);
    }

    const handler = ROUTES[endpoint];
    if (!handler) {
      console.warn('[mock-fetch] no route for', endpoint, '→ returning {}');
      return json({});
    }
    try {
      return json(handler(url, init));
    } catch (err) {
      console.error('[mock-fetch] handler error for', endpoint, err);
      return json({});
    }
  };

  console.debug('[mock-fetch] fetch interceptor installed for', API_BASE);
})();
