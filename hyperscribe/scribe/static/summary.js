import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup, parseAPBlocks, matchCondition } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';
import { collectQuestionnaireScores } from '/plugin-io/api/hyperscribe/scribe/static/questionnaire-score.js';
import { useRecording } from '/plugin-io/api/hyperscribe/scribe/static/recording-hook.js';
import { initAuditLog, logEvent } from '/plugin-io/api/hyperscribe/scribe/static/audit-log.js';
import { connectScribeWS } from '/plugin-io/api/hyperscribe/scribe/static/scribe-ws.js';
import { FinishRecordingButton } from '/plugin-io/api/hyperscribe/scribe/static/finish-button.js';

const html = htm.bind(h);

function formatTime(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function TranscriptEntry({ speaker, start_offset_ms, text, is_final, providerName, providerPhotoUrl, patientName }) {
  const s = (speaker || '').toUpperCase();
  const isUnspecified = !s || s === 'UNSPECIFIED';
  const isProvider = s === 'DOCTOR' || s.includes('PROVIDER') || s.includes('DOCTOR');
  const isPatient = s === 'PATIENT' || s.includes('PATIENT');
  const time = formatTime(start_offset_ms);

  if (!is_final && isUnspecified) {
    return html`
      <div class="transcript-entry partial">
        <div class="entry-avatar listening">...</div>
        <div class="entry-content">
          <div class="entry-meta">
            <span class="entry-speaker listening-label">Listening</span>
            <span class="entry-time">${time}</span>
          </div>
          <p class="entry-text">${text}</p>
        </div>
      </div>
    `;
  }

  const role = isProvider ? 'provider' : isPatient ? 'patient' : 'unspecified';
  const label = isProvider ? (providerName || 'Provider') : isPatient ? (patientName || 'Patient') : 'Unspecified';
  const initial = isProvider ? 'Dr' : isPatient ? 'Pt' : '?';

  return html`
    <div class="transcript-entry ${is_final ? '' : 'partial'}">
      ${isProvider && providerPhotoUrl
        ? html`<img class="entry-avatar-img" src=${providerPhotoUrl} alt=${label} />`
        : html`<div class="entry-avatar ${role}">${initial}</div>`}
      <div class="entry-content">
        <div class="entry-meta">
          <span class="entry-speaker">${label}</span>
          <span class="entry-time">${time}</span>
        </div>
        <p class="entry-text">${text}</p>
      </div>
    </div>
  `;
}


function VerificationSummary({ result }) {
  const [expanded, setExpanded] = useState(false);
  const total = result.verified.length + result.failed.length;
  const headline = result.ok
    ? `All ${total} command(s) inserted successfully`
    : `${result.failed.length} of ${total} command(s) failed to insert`;
  return html`
    <div class="verification-banner ${result.ok ? 'verification-ok' : 'verification-error'}">
      <div class="verification-headline" onClick=${() => setExpanded(prev => !prev)}>
        <span>${headline}</span>
        <span class="verification-chevron ${expanded ? 'open' : ''}">\u25BE</span>
      </div>
      ${expanded && html`
        <div class="verification-details">
          ${result.failed.length > 0 && html`
            <div class="verification-group verification-group-failed">
              ${result.failed.map(f => html`
                <div class="verification-item" key=${f.command_uuid}>
                  <span class="verification-tag failed-tag">${f.command_type}</span>
                  <span>${f.display || ''}</span>
                </div>
              `)}
            </div>
          `}
          ${result.verified.map(v => html`
            <div class="verification-item" key=${v.command_uuid}>
              <span class="verification-tag passed-tag">${v.command_type}</span>
              <span>${v.display || ''}</span>
            </div>
          `)}
        </div>
      `}
    </div>
  `;
}

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

const SOAP_GROUPS = [
  { title: 'SUBJECTIVE', color: 'subjective', keys: new Set(['chief_complaint', 'history_of_present_illness', 'review_of_systems']) },
  { title: 'HISTORY', color: 'history', keys: new Set(['past_medical_history', 'past_surgical_history',
    'past_obstetric_history', 'family_history', 'social_history']) },
  { title: 'OBJECTIVE', color: 'objective', keys: new Set(['vitals', 'physical_exam', 'lab_results', 'imaging_results',
    'current_medications', 'allergies', 'immunizations']) },
  { title: 'ASSESSMENT & PLAN', color: 'plan', keys: new Set(['plan', 'assessment_and_plan', 'prescription', 'appointments']) },
  { title: 'CHARGES', color: 'charges', keys: new Set(['charges']) },
];

// KOALA-5485: section_keys whose already-documented commands can be edited
// during amendment. RFV (chief_complaint) goes through a direct EDIT effect;
// CustomCommand-routed sections (_ros, _history_review, _chart_review,
// physical_exam, lab_results, imaging_results) go through EnterInError +
// Originate; everything else goes through EnterInError + Originate + Commit.
//
// Covers every command_type in `_BUILDERS` EXCEPT orders (prescribe, refill,
// adjust_prescription, refer, imaging_order, lab_order) and questionnaires
// (which need a 4-effect amend route, deferred to a follow-up ticket).
//
// MIRRORED in three places - keep all in sync until single-sourcing lands
// (follow-up ticket):
//   - hyperscribe/scribe/commands/builder.py (EDITABLE_AMEND_SECTIONS)
//   - hyperscribe/scribe/static/summary.js (this file)
//   - hyperscribe/scribe/static/soap-group.js (EDITABLE_AMEND_SECTIONS)
const EDITABLE_AMEND_SECTIONS = new Set([
  // DIRECT_EDIT
  'chief_complaint',
  // CUSTOM_COMMAND_ROUTED
  '_ros',
  '_history_review',
  '_chart_review',
  'physical_exam',
  'lab_results',
  'imaging_results',
  // VOID_RECREATE - SOAP-section-anchored
  'history_of_present_illness',
  'current_medications',
  'allergies',
  'vitals',
  'past_medical_history',
  'past_surgical_history',
  'family_history',
  'assessment_and_plan',
  'plan',
  // VOID_RECREATE - ad-hoc buckets (rows added during a session retain these
  // section_keys after approval+reload).
  '_ad_hoc',
  '_objective_ad_hoc',
  '_history_ad_hoc',
  '_subjective_ad_hoc',
  '_charges_ad_hoc',
]);

// Command types that MUST NEVER be amended, regardless of section_key.
// Three reasons a command_type lands here (see builder.py for fuller writeup):
//   1. STRUCTURALLY IMPOSSIBLE: no COMMIT_*_COMMAND interpreter in home-app.
//   2. STRUCTURALLY AWKWARD: EIE works, no COMMIT - needs a 4-effect route.
//   3. POLICY EXCLUDED: full wiring exists, but amend-after-dispatch is the
//      wrong abstraction (a cancel/resend workflow is the right shape).
//
// Both lists work together: section_key gates "is this an amendable spot in
// the UI?", and command_type gates "is this kind of action safe to void
// and recreate?". An order added via the _ad_hoc bucket would pass the
// section gate but must still be denied by the command gate.
//
// Questionnaire IS amendable now (originate(commit=True) shortcut — backend
// emits EIE + originate-with-values-and-commit, 2 effects).
//
// MIRRORED with builder.py's NON_EDITABLE_AMEND_COMMAND_TYPES.
const NON_EDITABLE_AMEND_COMMAND_TYPES = new Set([
  // 1. Structurally impossible (no COMMIT_*_COMMAND interpreter):
  'prescribe',
  'refill',
  'adjust_prescription',
  // 2. Structurally awkward (EIE exists, no COMMIT - 4-effect route needed):
  'refer',
  'imaging_order',
  // 3. Policy excluded (full wiring exists; amend after lab-partner ticket
  //    dispatch creates downstream confusion - cancel/resend is the right shape):
  'lab_order',
]);

function isAmendingSectionEditable(command, isAmending) {
  // During amendment, allow editing iff (a) we're in amendment mode (wasFinalized
  // && !approved), (b) the section is in the allowlist, (c) the command_type
  // is not in the denylist (orders, questionnaire), and (d) the command was
  // originally inserted by Scribe (has a command_uuid we can target). New
  // ad-hoc commands added during amendment go through the normal insert path.
  return Boolean(
    isAmending &&
    command &&
    command.command_uuid &&
    EDITABLE_AMEND_SECTIONS.has(command.section_key) &&
    !NON_EDITABLE_AMEND_COMMAND_TYPES.has(command.command_type)
  );
}

const SKELETON_SECTIONS = [
  { key: 'chief_complaint', title: 'Chief Complaint', text: '' },
  { key: 'history_of_present_illness', title: 'History of Present Illness', text: '' },
  { key: 'past_medical_history', title: 'Past Medical History Discussed During Encounter', text: '' },
  { key: 'past_surgical_history', title: 'Past Surgical History', text: '' },
  { key: 'family_history', title: 'Family History', text: '' },
  { key: 'social_history', title: 'Social History', text: '' },
  { key: 'vitals', title: 'Vitals', text: '' },
  { key: 'physical_exam', title: 'Physical Exam', text: '' },
  { key: 'current_medications', title: 'Meds Discussed', text: '' },
  { key: 'allergies', title: 'Allergies Discussed', text: '' },
  { key: 'assessment_and_plan', title: 'Assessment & Plan', text: '' },
];

const FINALIZE_LABEL = 'Finalizing transcript';
const PROGRESS_STEPS = [
  'Generating note',
  'Structuring the note',
  'Extracting commands',
  'Generating recommendations',
  'Suggesting diagnoses',
];
// Total steps shown to the user = "Finalizing transcript" + the server-driven
// SUMMARY_STEPS pipeline. Used for the % progress calculation.
const TOTAL_PROGRESS_STEPS = PROGRESS_STEPS.length + 1;

function buildCommandBySectionKey(commands) {
  const map = {};
  commands.forEach((cmd, index) => {
    if (cmd.section_key) {
      if (!map[cmd.section_key]) {
        map[cmd.section_key] = [];
      }
      map[cmd.section_key].push({ command: cmd, index });
    }
  });
  return map;
}

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onDeleteCommand, { adHocCommands, objectiveAdHocCommands, historyAdHocCommands, subjectiveAdHocCommands, chargeAdHocCommands, assignees, onAddTask, onAddOrder, onAddPlan, onAddMedication, onAddAllergy, onAddStopMedication, onAddRemoveAllergy, onAddResolveCondition, onAddHistory, onAddQuestionnaire, onAddCharge, onAddTemplateCharge, onRemoveChargeByCpt, templateCharges, readOnly, isAmending, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onRejectRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions, onAddNow, onAddVitals, hideRejected, alertFacilityEnabled, onEditingChange, questionnaireScores } = {}) {
  return SOAP_GROUPS
    .map(group => {
      const matching = sections.filter(s => group.keys.has(s.key.toLowerCase()));
      const isPlan = group.title === 'ASSESSMENT & PLAN';
      const isObjective = group.title === 'OBJECTIVE';
      const isHistory = group.title === 'HISTORY';
      const isSubjective = group.title === 'SUBJECTIVE';
      const isCharges = group.title === 'CHARGES';
      return html`<${SoapGroup}
        key=${group.title}
        title=${group.title}
        groupColor=${group.color}
        sections=${matching}
        commandBySectionKey=${commandBySectionKey}
        onEditCommand=${onEditCommand}
        onDeleteCommand=${onDeleteCommand}
        adHocCommands=${isPlan ? adHocCommands : isObjective ? objectiveAdHocCommands : isHistory ? historyAdHocCommands : isSubjective ? subjectiveAdHocCommands : isCharges ? chargeAdHocCommands : null}
        assignees=${isPlan ? assignees : null}
        onAddTask=${isPlan ? onAddTask : null}
        onAddOrder=${isPlan ? onAddOrder : null}
        onAddPlan=${isPlan ? onAddPlan : null}
        onAddVitals=${isObjective ? onAddVitals : null}
        onAddMedication=${isObjective ? onAddMedication : null}
        onAddAllergy=${isObjective ? onAddAllergy : null}
        onAddStopMedication=${isObjective ? onAddStopMedication : null}
        onAddRemoveAllergy=${isObjective ? onAddRemoveAllergy : null}
        onAddResolveCondition=${isPlan ? onAddResolveCondition : null}
        onAddHistory=${isHistory ? onAddHistory : null}
        onAddQuestionnaire=${isSubjective ? onAddQuestionnaire : null}
        onAddCharge=${isCharges ? onAddCharge : null}
        onAddTemplateCharge=${isCharges ? onAddTemplateCharge : null}
        onRemoveChargeByCpt=${isCharges ? onRemoveChargeByCpt : null}
        templateCharges=${isCharges ? templateCharges : null}
        readOnly=${readOnly}
        isAmending=${isAmending}
        sectionConditions=${sectionConditions}
        patientId=${patientId}
        noteId=${noteId}
        staffId=${staffId}
        staffName=${staffName}
        recommendations=${(isObjective || isPlan) ? recommendations : null}
        onEditRecommendation=${(isObjective || isPlan) ? onEditRecommendation : null}
        onDeleteRecommendation=${(isObjective || isPlan) ? onDeleteRecommendation : null}
        onRejectRecommendation=${(isObjective || isPlan) ? onRejectRecommendation : null}
        onAcceptRecommendation=${(isObjective || isPlan) ? onAcceptRecommendation : null}
        onAddCondition=${isPlan ? onAddCondition : null}
        unmatchedConditions=${isPlan ? unmatchedConditions : null}
        diagnosisSuggestions=${isPlan ? diagnosisSuggestions : null}
        onAddNow=${(isPlan || isObjective) ? onAddNow : null}
        hideRejected=${hideRejected}
        alertFacilityEnabled=${alertFacilityEnabled}
        onEditingChange=${onEditingChange}
        questionnaireScores=${isObjective ? questionnaireScores : null}
      />`;
    })
    .filter(Boolean);
}

export function Scribe({ noteId, patientId, staffId, staffName, providerName, providerPhotoUrl, patientName, patientBirthDate, patientGender, debugMode, noteEditable = true, isAuthor = false, alertFacilityEnabled = false, initialData = null }) {
  const initSummary = initialData?.summary ?? null;
  const [noteData, setNoteData] = useState(initSummary?.note ?? null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [commands, setCommands] = useState(initSummary?.commands ?? []);
  const [inserting, setInserting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [approved, setApproved] = useState(initSummary?.approved ?? false);
  // Fall back to `approved` so pre-existing finalized notes (saved before the
  // was_finalized latch shipped) still surface the amendment pill on open.
  // New rows ride the explicit latch from _save_summary.
  const [wasFinalized, setWasFinalized] = useState(
    initSummary?.was_finalized ?? !!initSummary?.approved
  );
  const [isNoteEditable, setNoteEditable] = useState(noteEditable);
  const [hideRejected, setHideRejected] = useState(true);
  const [assignees, setAssignees] = useState(initialData?.assignees ?? []);
  const [recommendations, setRecommendations] = useState(initSummary?.recommendations ?? []);
  const [sectionConditions, setSectionConditions] = useState({});
  const [unmatchedConditions, setUnmatchedConditions] = useState(initSummary?.unmatched_conditions ?? []);
  const [diagnosisSuggestions, setDiagnosisSuggestions] = useState(initSummary?.diagnosis_suggestions ?? {});
  const [progress, setProgress] = useState({ step: -1, total: 0, label: '' });
  const [verificationResult, setVerificationResult] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Template state.
  const [templates, setTemplates] = useState(initialData?.templates ?? []);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [mode, setMode] = useState(() => {
    const cached = initSummary?.mode ?? null;
    // Dead state recovery: ai mode was persisted but recording was never started (e.g.
    // mic failure persisted mode before startRecording could revert it). Only applies
    // to 'ai' — manual mode legitimately has no transcript.
    if (cached === 'ai' && !initSummary?.note && !initialData?.transcript?.started) {
      return null;
    }
    return cached;
  });
  const [transcriptCollapsed, setTranscriptCollapsed] = useState(false);
  // Auto-scroll the transcript body to the latest entry whenever live capture
  // is producing or refining content. We deliberately don't try to "respect"
  // a user's scroll-up while recording — clinicians want to keep seeing the
  // running transcription as proof the capture is working, and the scroll
  // would just keep losing fights with new entries anyway. Once the session
  // is finalized, entries stop changing and the user can scroll freely.
  const transcriptBodyRef = useRef(null);
  const [cachedTemplateName, setCachedTemplateName] = useState(initSummary?.selected_template_name ?? null);
  const cacheLoadedRef = useRef(!!initialData);
  const addNowAttemptedRef = useRef([]);
  // Set to true after the first save-summary 403 (`_authorize_edit` denial:
  // note locked or wrong author). Gates subsequent autosaves so the Scribe
  // tab doesn't fire one POST per state change against a note it can't
  // actually save to. Brigade was generating ~11.9k of these in 14 days.
  const saveBlockedRef = useRef(false);

  const [editingFields, setEditingFields] = useState(new Set());

  // Recording hook.
  const recording = useRecording(noteId, initialData?.transcript);

  // Keep the transcript pinned to the latest entry as new ones stream in or
  // get refined (in-place partial updates, speaker-attribution flips, etc.).
  // RAF defers the scroll until after layout so scrollHeight reflects the
  // post-update height. Skipped once the recording is finalized so we don't
  // yank a user reading the saved transcript on later mounts.
  useEffect(() => {
    if (transcriptCollapsed) return;
    if (recording.finalized) return;
    const el = transcriptBodyRef.current;
    if (!el) return;
    const rafId = requestAnimationFrame(() => {
      const node = transcriptBodyRef.current;
      if (!node) return;
      node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(rafId);
  }, [recording.entries, transcriptCollapsed, recording.finalized]);

  const [showSavedToast, setShowSavedToast] = useState(false);
  useEffect(() => {
    if (!recording.lastSaved) return;
    logEvent('TRANSCRIPT_AUTO_SAVED', { entryCount: recording.entries.length });
    setShowSavedToast(true);
    const timer = setTimeout(() => setShowSavedToast(false), 2000);
    return () => clearTimeout(timer);
  }, [recording.lastSaved]);

  // Audit logging.
  useEffect(() => { initAuditLog(noteId); }, [noteId]);

  // WebSocket: listen for note state changes in real time.
  useEffect(() => {
    if (!noteId) return;
    const cleanup = connectScribeWS(noteId, (msg) => {
      if (msg.type === 'NOTE_STATE_CHANGED') {
        setNoteEditable(msg.editable);
      }
    });
    return cleanup;
  }, [noteId]);

  const noteLocked = !isNoteEditable && !approved;
  const canEdit = isAuthor && isNoteEditable && !approved;
  // Lock takes precedence over authorship in the banner messaging.
  const readOnlyReason = noteLocked
    ? 'locked'
    : (!isAuthor && !approved ? 'non_author' : null);

  const saveSummaryToCache = useCallback(async (note, cmds, isApproved, extras = {}) => {
    // Skip the request entirely when we already know the server will reject
    // it: non-author viewers and locked notes both fail `_authorize_edit`
    // server-side. The read-only banner elsewhere already covers these cases
    // visually; no point firing a request to be told "no" again.
    if (!isAuthor) return;
    if (!isNoteEditable) return;
    // Once the server has rejected an autosave for this note (typical cause:
    // the note finalized while the Scribe tab was still attached), stop
    // sending. The note can't become editable again without an explicit user
    // action (Amend / state change), and those paths reset isNoteEditable
    // via the NOTE_STATE_CHANGED WS message — they don't go through here.
    if (saveBlockedRef.current) return;
    try {
      const res = await fetch(`${API_BASE}/save-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, note, commands: cmds, approved: isApproved, ...extras }),
      });
      if (res.status === 403) {
        // _authorize_edit denial — "Note is not editable" or "Only the note
        // author can modify the Scribe tab". Gate further autosaves silently;
        // the existing locked / non-author banner already explains why edits
        // aren't sticking.
        saveBlockedRef.current = true;
      }
    } catch (err) {
      console.error('Failed to save summary to cache:', err);
    }
  }, [noteId, isAuthor, isNoteEditable]);

  // Resetting the gate when the note becomes editable again (post-Amend, or
  // the user re-loads onto a fresh note in the same iframe). isNoteEditable
  // flips via the NOTE_STATE_CHANGED WS message — see the listener above.
  useEffect(() => {
    if (isNoteEditable) saveBlockedRef.current = false;
  }, [isNoteEditable, noteId]);

  const handleMakeChanges = useCallback(() => {
    if (!isAuthor || !isNoteEditable || !approved) return;
    // Either `already_documented` OR `command_uuid` means "already on the note"
    // — same predicate as the `insertable` filter (see 8ea1df36 back-compat
    // fix). Pre-existing finalized notes (signed before the explicit
    // already_documented stamping shipped) carry command_uuid but not the
    // explicit flag; using `already_documented` alone here would wipe every
    // such command on Make Changes. command_uuid is the authoritative
    // "on the note" signal.
    const onNote = (c) => c.already_documented || c.command_uuid;
    const documentedCount = commands.filter(onNote).length;
    logEvent('AMENDMENT_STARTED', {
      commands_at_start: documentedCount,
      dropped_commands: commands.length - documentedCount,
      dropped_recommendations: recommendations.length,
    });
    // Scribe should mirror the signed note during amendment: drop AI recs that
    // never made it into the note. Leaving them in state would also re-insert
    // them on re-Approve via the `insertable` filter.
    setCommands(prev => prev.filter(onNote));
    setRecommendations([]);
    setUnmatchedConditions([]);
    setDiagnosisSuggestions({});
    setApproved(false);
    // Optimistically keep wasFinalized=true; it's a one-way latch server-side
    // already, but ensure the React state matches without waiting for the
    // /summary refetch.
    setWasFinalized(true);
  }, [isAuthor, isNoteEditable, approved, commands, recommendations]);

  // Load summary from cache — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;

    async function loadOrGenerate() {
      try {
        const cacheRes = await fetch(`${API_BASE}/summary?note_id=${encodeURIComponent(noteId)}`);
        if (!cancelled) {
          const cached = await cacheRes.json();
          // Restore cached template name (resolved against templates once they load).
          if (cached.selected_template_name) {
            setCachedTemplateName(cached.selected_template_name);
          }
          if (cached.mode) {
            setMode(cached.mode);
          }
          if (cached.approved) {
            setApproved(true);
          }
          // Treat cached.approved as implying was_finalized for pre-existing
          // finalized notes that predate the explicit latch.
          if (cached.was_finalized || cached.approved) {
            setWasFinalized(true);
          }
          if (cached.note) {
            // Full cached summary — restore everything.
            setNoteData(cached.note);
            setCommands(cached.commands || []);
            setRecommendations(cached.recommendations || []);
            setUnmatchedConditions(cached.unmatched_conditions || []);
            setDiagnosisSuggestions(cached.diagnosis_suggestions || {});
            // Repopulate Add Now attempted entries from cached items for verification merge.
            addNowAttemptedRef.current = [
              ...(cached.commands || []),
              ...(cached.recommendations || []),
            ]
              .filter(c => c._added_now && c.command_uuid)
              .map(c => ({
                command_uuid: c.command_uuid,
                command_type: c.command_type,
                display: (c.display || '').slice(0, 80),
              }));
            logEvent('CACHE_LOADED', { hasNote: !!cached.note, commandCount: (cached.commands || []).length });
            return;
          }
          // Cache without note — restore ad-hoc commands and mode.
          if (cached.commands && cached.commands.length > 0) {
            setCommands(cached.commands);
            logEvent('CACHE_LOADED', { hasNote: false, commandCount: cached.commands.length });
          }
        }
      } catch (err) {
        // Cache miss — start with empty skeleton.
      } finally {
        cacheLoadedRef.current = true;
      }
    }

    loadOrGenerate();
    return () => { cancelled = true; };
  }, [noteId]);

  // Poll progress while generating.
  useEffect(() => {
    if (!generating) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/summary-progress?note_id=${encodeURIComponent(noteId)}`);
        const data = await res.json();
        setProgress(data);
      } catch (err) {
        // Ignore polling errors.
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [generating, noteId]);

  // Auto-save commands to cache (debounced) so ad-hoc items added before generation persist on reload.
  // Skip until cache has loaded to avoid overwriting persisted noteData with null.
  const commandsSaveRef = useRef(null);
  useEffect(() => {
    if (!cacheLoadedRef.current) return;
    if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current);
    commandsSaveRef.current = setTimeout(() => {
      saveSummaryToCache(noteData, commands, approved || inserting, {
        recommendations,
        unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions,
        selected_template_name: selectedTemplate?.name || null,
        mode: mode,
      });
    }, 500);
    return () => { if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current); };
  }, [commands, recommendations, selectedTemplate, mode, approved, inserting]);

  // Auto-verify on load when approved with command UUIDs.
  useEffect(() => {
    if (!approved || verificationResult) return;
    const withUuids = [
      ...commands.filter(c => c.command_uuid),
      ...recommendations.filter(c => c.command_uuid),
    ];
    if (withUuids.length === 0) return;
    const attempted = withUuids.map(c => ({
      command_uuid: c.command_uuid,
      command_type: c.command_type,
      display: (c.display || '').slice(0, 80),
    }));
    let cancelled = false;
    async function verify() {
      try {
        const res = await fetch(`${API_BASE}/verify-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, attempted }),
        });
        const data = await res.json();
        if (cancelled) return;
        const failedCount = data.failed?.length || 0;
        setVerificationResult(failedCount > 0
          ? { ok: false, verified: data.verified || [], failed: data.failed }
          : { ok: true, verified: data.verified || [], failed: [] });
      } catch (err) {
        console.error('Auto-verify failed:', err);
      }
    }
    verify();
    return () => { cancelled = true; };
  }, [approved, noteId, commands, recommendations]);

  const handleGenerate = useCallback(async () => {
    logEvent('GENERATE_START');
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/generate-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          note_uuid: noteId,
          patient_id: patientId,
          template_ros_sections: selectedTemplate?.ros_sections || null,
          template_pe_sections: selectedTemplate?.pe_sections || null,
          patient_context: {
            name: patientName || '',
            birth_date: patientBirthDate || '',
            gender: patientGender || '',
          },
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        logEvent('GENERATE_ERROR', { error: data.error });
      } else {
        const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
        const existingAdHoc = commands.filter(c => adHocKeys.has(c.section_key));
        const generated = data.commands || [];
        const generatedTypes = new Set(generated.map(c => c.command_type));
        const templateKeep = commands.filter(c =>
          c._template_inserted && !adHocKeys.has(c.section_key) && !generatedTypes.has(c.command_type)
        );
        const newCommands = [...generated, ...existingAdHoc, ...templateKeep];
        const newRecs = data.recommendations || [];
        setNoteData(data.note);
        setCommands(newCommands);
        setRecommendations(newRecs);
        setSectionConditions(data.section_conditions || {});
        setUnmatchedConditions(data.unmatched_conditions || []);
        setDiagnosisSuggestions(data.diagnosis_suggestions || {});
        // Save to cache immediately so a refresh doesn't lose the generated note.
        saveSummaryToCache(data.note, newCommands, false, {
          recommendations: newRecs,
          unmatched_conditions: data.unmatched_conditions || [],
          diagnosis_suggestions: data.diagnosis_suggestions || {},
          selected_template_name: selectedTemplate?.name || null,
          mode: mode,
        });
        logEvent('GENERATE_COMPLETE', { commandCount: (data.commands || []).length, recCount: (data.recommendations || []).length });
      }
    } catch (err) {
      setError('Failed to generate summary');
      logEvent('GENERATE_ERROR', { error: err.message });
    } finally {
      setGenerating(false);
    }
  }, [noteId, selectedTemplate, commands, mode]);

  // Fetch assignees for task assignment (independent, small).
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;
    async function fetchAssignees() {
      try {
        const res = await fetch(`${API_BASE}/assignees`, { cache: 'no-store' });
        if (cancelled) return;
        const data = await res.json();
        if (data.assignees) setAssignees(data.assignees);
      } catch (err) {
        console.error('Failed to fetch assignees:', err);
      }
    }
    fetchAssignees();
    return () => { cancelled = true; };
  }, []);

  // Load visit templates on mount — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;
    async function loadTemplates() {
      try {
        const res = await fetch(`${API_BASE}/visit-templates`);
        const data = await res.json();
        if (!cancelled && data.templates) setTemplates(data.templates);
      } catch (err) {
        console.error('Failed to load visit templates:', err);
      }
    }
    loadTemplates();
    return () => { cancelled = true; };
  }, []);

  // Restore selected template from cache once templates are loaded.
  useEffect(() => {
    if (cachedTemplateName && templates.length > 0 && !selectedTemplate) {
      const match = templates.find(t => t.name === cachedTemplateName);
      if (match) setSelectedTemplate(match);
    }
  }, [cachedTemplateName, templates, selectedTemplate]);

  // Auto-generate summary after recording finishes.
  const prevFinalizedRef = useRef(false);
  useEffect(() => {
    if (recording.finalized && !prevFinalizedRef.current) {
      // Collapse transcript once recording is done.
      setTranscriptCollapsed(true);
      // Only auto-generate if cache has loaded (prevents regeneration on reload when
      // noteData hasn't been restored yet from cache).
      if (cacheLoadedRef.current && mode === 'ai' && !noteData && !generating) {
        handleGenerate();
      }
    }
    prevFinalizedRef.current = recording.finalized;
  }, [recording.finalized, mode, noteData, generating, handleGenerate]);

  // Warn before navigating away during recording or insertion.
  const activeRecording = recording.status === 'recording';
  useEffect(() => {
    if (!inserting && !activeRecording) return;
    const handler = (e) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [inserting, activeRecording]);

  // Set mode to 'ai' if we load a finalized transcript from cache (returning to a previous session).
  useEffect(() => {
    if (recording.finalized && mode === null && !noteData && !approved) {
      setMode('ai');
    }
  }, [recording.finalized, mode, noteData, approved]);


  const handleSelectTemplate = useCallback((e) => {
    if (!canEdit) return;
    const templateName = e.target.value;
    if (!templateName) {
      logEvent('DESELECT_TEMPLATE');
      setSelectedTemplate(null);
      setCommands(prev => prev.filter(c => !c._template_inserted));
      saveSummaryToCache(noteData, commands, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: null,
      });
      return;
    }
    logEvent('SELECT_TEMPLATE', { name: templateName });
    const tmpl = templates.find(t => t.name === templateName);
    if (!tmpl) return;
    setSelectedTemplate(tmpl);

    // Build questionnaire commands from the resolved template data.
    const qCommands = tmpl.questionnaires.map(q => ({
      command_type: 'questionnaire',
      display: q.questionnaire_name,
      data: {
        questionnaire_dbid: q.questionnaire_dbid,
        questionnaire_name: q.questionnaire_name,
        is_scored: !!q.is_scored,
        scoring_function_name: q.scoring_function_name || '',
        questions: q.questions.map(question => ({
          dbid: question.dbid,
          label: question.label,
          type: question.type,
          responses: question.options.map(o => ({
            dbid: o.dbid,
            value: (question.type === 'TXT' || question.type === 'INT') ? '' : o.value,
            code: o.code || '',
            score_value: o.score_value || '',
            selected: false,
            comment: null,
          })),
        })),
      },
      selected: true,
      section_key: '_subjective_ad_hoc',
      already_documented: false,
      _template_inserted: true,
    }));

    const templateCommands = [...qCommands];

    if (tmpl.ros_sections && tmpl.ros_sections.length > 0) {
      templateCommands.push({
        command_type: 'ros',
        display: tmpl.ros_sections.map(s => s.title).join(' | '),
        data: { sections: tmpl.ros_sections },
        selected: true,
        section_key: '_ros',
        already_documented: false,
        _template_inserted: true,
      });
    }

    if (tmpl.pe_sections && tmpl.pe_sections.length > 0) {
      templateCommands.push({
        command_type: 'physical_exam',
        display: tmpl.pe_sections.map(s => s.title).join(' | '),
        data: { sections: tmpl.pe_sections },
        selected: true,
        section_key: 'physical_exam',
        already_documented: false,
        _template_inserted: true,
      });
    }

    // Replace previous template commands, keep everything else.
    setCommands(prev => {
      const nonTemplate = prev.filter(c => !c._template_inserted);
      const updated = [...nonTemplate, ...templateCommands];
      saveSummaryToCache(noteData, updated, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: tmpl.name,
      });
      return updated;
    });
  }, [templates, noteData, approved, canEdit, recommendations, unmatchedConditions, diagnosisSuggestions, saveSummaryToCache]);

  const handleStartAI = useCallback(async () => {
    if (!canEdit) return;
    logEvent('START_AI');
    setMode('ai');
    const ok = await recording.startRecording();
    if (!ok) {
      logEvent('START_AI_FAILED');
      setMode(null);
    }
  }, [recording, canEdit]);

  const handleStartManual = useCallback(() => {
    if (!canEdit) return;
    logEvent('START_MANUAL');
    setMode('manual');
    // Pre-populate empty commands for all narrative sections so they render as editable text areas.
    const manualCommands = [
      { command_type: 'rfv', display: '', data: { comment: '' }, selected: true, section_key: 'chief_complaint', already_documented: false },
      { command_type: 'hpi', display: '', data: { narrative: '' }, selected: true, section_key: 'history_of_present_illness', already_documented: false },
      { command_type: 'vitals', display: '', data: {}, selected: true, section_key: 'vitals', already_documented: false },
      { command_type: 'plan', display: '', data: { narrative: '' }, selected: true, section_key: 'assessment_and_plan', already_documented: false },
    ];
    // Add PE from template if available.
    if (selectedTemplate?.pe_sections?.length > 0) {
      const peSections = selectedTemplate.pe_sections.map(s => ({ key: s.key, title: s.title, text: s.text, updated: false, template_text: s.text }));
      const peDisplay = peSections.map(s => s.title).join(' | ');
      manualCommands.push({ command_type: 'physical_exam', display: peDisplay, data: { sections: peSections }, selected: true, section_key: 'physical_exam', already_documented: false });
    }
    setCommands(prev => {
      // Keep any existing ad-hoc commands and template-inserted commands (ROS, PE, questionnaires).
      const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
      const existing = prev.filter(c => {
        if (c._template_inserted && c.command_type === 'physical_exam') return false;
        return adHocKeys.has(c.section_key) || c._template_inserted;
      });
      return [...manualCommands, ...existing];
    });
  }, [selectedTemplate, canEdit]);


  // Compute unmatched conditions when loading from old cache format (no unmatched_conditions key).
  useEffect(() => {
    // Only run for cache loads where we have commands + sectionConditions but no unmatched_conditions.
    if (!noteData || !commands.length || unmatchedConditions.length > 0) return;
    if (!sectionConditions || !Object.keys(sectionConditions).length) return;
    const hasDiagnose = commands.some(c => c.command_type === 'diagnose');
    const hasPlan = commands.some(c =>
      c.command_type === 'plan' && ['assessment_and_plan', 'plan'].includes(c.section_key)
    );
    if (!hasDiagnose || hasPlan) return;

    const codes = sectionConditions['assessment_and_plan'] || sectionConditions['plan'] || [];
    if (!codes.length) return;
    const matchedSet = new Set();
    commands.filter(c => c.command_type === 'diagnose').forEach(c => {
      const m = matchCondition(c.data.condition_header || '', codes);
      if (m) matchedSet.add(m);
    });
    setUnmatchedConditions(codes.filter(c => !matchedSet.has(c)));
  }, [sectionConditions, commands, noteData, unmatchedConditions]);


  const handleEdit = useCallback((index, newData, newType) => {
    logEvent('EDIT_COMMAND', { index, commandType: newType || commands[index]?.command_type, sectionKey: commands[index]?.section_key, data: newData });
    if (!canEdit) return;
    // KOALA-5485: during amendment, edits to already-documented commands in
    // EDITABLE_AMEND_SECTIONS are routed through /edit-existing-commands on
    // Save changes. Tag the row so handleInsert can split it out from the
    // normal insertable filter.
    //
    // The tag is applied UNIFORMLY at the bottom of the per-command branch
    // (single tag point) so every command_type participates in the amend
    // split. The gate `isAmendingSectionEditable` is the authoritative
    // eligibility filter: it checks `wasFinalized && !approved` (we're
    // amending), `command_uuid` presence (Scribe-inserted, not freshly
    // ad-hoc), section_key allowlist, and command_type denylist. Orders
    // (prescribe, refill, adjust_prescription, refer, imaging_order,
    // lab_order), questionnaire, and freshly-added ad-hoc rows are correctly
    // excluded by the gate, not by per-branch tag omission.
    const isAmendEdit = (cmd) => isAmendingSectionEditable(cmd, wasFinalized && !approved);
    setCommands(prev => {
      const updated = prev.map((cmd, i) => {
        if (i !== index) return cmd;
        const type = newType || cmd.command_type;
        let next;
        if (type === 'history_review' || type === 'chart_review' || type === 'ros' || type === 'physical_exam') {
          const display = (newData.sections || []).map(s => s.title).join(' | ');
          next = { ...cmd, data: newData, display };
        } else if (type === 'vitals') {
          const vParts = [];
          const sys = newData.blood_pressure_systole;
          const dia = newData.blood_pressure_diastole;
          if (sys != null && dia != null) vParts.push(`BP ${sys}/${dia} mmHg`);
          if (newData.pulse != null) vParts.push(`HR ${newData.pulse} bpm`);
          if (newData.respiration_rate != null) vParts.push(`RR ${newData.respiration_rate} /min`);
          if (newData.oxygen_saturation != null) vParts.push(`SpO2 ${newData.oxygen_saturation}%`);
          if (newData.body_temperature != null) vParts.push(`Temp ${newData.body_temperature} °F`);
          if (newData.height != null) vParts.push(`Height ${newData.height} in`);
          if (newData.weight_lbs != null) vParts.push(`Weight ${newData.weight_lbs} lbs`);
          if (newData.blood_pressure_position_and_site != null) {
            const siteLabels = {
              0: 'Sitting, Right Upper Arm', 1: 'Sitting, Left Upper Arm',
              2: 'Sitting, Right Lower Arm', 3: 'Sitting, Left Lower Arm',
              4: 'Standing, Right Upper Arm', 5: 'Standing, Left Upper Arm',
              6: 'Standing, Right Lower Arm', 7: 'Standing, Left Lower Arm',
              8: 'Supine, Right Upper Arm', 9: 'Supine, Left Upper Arm',
              10: 'Supine, Right Lower Arm', 11: 'Supine, Left Lower Arm',
            };
            const label = siteLabels[newData.blood_pressure_position_and_site];
            if (label) vParts.push(`Site: ${label}`);
          }
          if (newData.note) vParts.push(`Note: ${newData.note}`);
          next = { ...cmd, data: newData, display: vParts.join(', ') || 'Vitals' };
        } else if (type === 'medication_statement') {
          next = { ...cmd, data: newData, display: newData.medication_text || '' };
        } else if (type === 'allergy') {
          next = { ...cmd, data: newData, display: newData.allergy_text || '' };
        } else if (type === 'task') {
          const parts = [newData.title || ''];
          if (newData.comment) parts.push(`Comment: ${newData.comment}`);
          next = { ...cmd, data: newData, display: parts.join(' \u2014 ') };
        } else if (type === 'prescribe' || type === 'refill' || type === 'adjust_prescription') {
          next = { ...cmd, command_type: type, data: newData, display: newData.medication_text || '' };
        } else if (type === 'lab_order') {
          const parts = [];
          if (newData.lab_partner_name) parts.push(newData.lab_partner_name);
          if (newData.test_names && newData.test_names.length) parts.push(newData.test_names.join(', '));
          if (newData.comment) parts.push(newData.comment);
          if (newData.fasting_required) parts.push('Fasting');
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || '' };
        } else if (type === 'imaging_order') {
          const parts = [newData.image_display, newData.additional_details, newData.comment, newData.priority].filter(Boolean);
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' | ') };
        } else if (type === 'refer') {
          const parts = [newData.refer_to_display, newData.clinical_question, newData.priority].filter(Boolean);
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || 'Referral' };
        } else if (type === 'familyHistory') {
          const parts = [newData.condition_display, newData.relative, newData.note].filter(Boolean);
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' — ') || '' };
        } else if (type === 'medicalHistory') {
          const parts = [newData.past_medical_history];
          const dates = [newData.approximate_start_date, newData.approximate_end_date].filter(Boolean);
          if (dates.length) parts.push(dates.join(' – '));
          if (newData.comments) parts.push(newData.comments);
          next = { ...cmd, command_type: type, data: newData, display: parts.filter(Boolean).join(' — ') || '' };
        } else if (type === 'surgicalHistory') {
          const parts = [newData.procedure_display];
          if (newData.approximate_date) parts.push(newData.approximate_date);
          if (newData.comment) parts.push(newData.comment);
          next = { ...cmd, command_type: type, data: newData, display: parts.filter(Boolean).join(' — ') || '' };
        } else if (type === 'questionnaire') {
          next = { ...cmd, command_type: type, data: newData, display: newData.questionnaire_name || '' };
        } else if (type === 'perform') {
          const display = newData.cpt_code ? `${newData.cpt_code} — ${newData.description || ''}` : '';
          next = { ...cmd, command_type: type, data: newData, display };
        } else if (type === 'stop_medication') {
          next = { ...cmd, command_type: type, data: newData, display: newData.medication_name || '' };
        } else if (type === 'remove_allergy') {
          next = { ...cmd, command_type: type, data: newData, display: newData.allergy_name || '' };
        } else if (type === 'resolve_condition') {
          next = { ...cmd, command_type: type, data: newData, display: newData.condition_name || '' };
        } else if (type === 'diagnose') {
          const display = newData.icd10_display || newData.condition_header || cmd.display;
          const accepted = newData.icd10_code ? (newData.accepted !== undefined ? newData.accepted : true) : false;
          const rejected = newData.rejected || false;
          next = { ...cmd, command_type: type, data: { ...newData, accepted, rejected }, display };
        } else if (type === 'assess') {
          next = { ...cmd, data: newData };
        } else {
          // Default path: rfv (chief_complaint), hpi (history_of_present_illness),
          // lab_results, imaging_results, plan, and any other narrative-shaped
          // command. rfv uses the `comment` field; everything else uses
          // `narrative`. Any of these can be amended during the amendment flow.
          const field = cmd.command_type === 'rfv' ? 'comment' : 'narrative';
          const text = newData[field] || '';
          next = { ...cmd, data: newData, display: text };
        }
        // Single tag point (KOALA-5485 silent no-op fix). The gate
        // `isAmendEdit` filters by section_key allowlist + command_type
        // denylist + command_uuid presence + amending mode. Without this,
        // edits to vitals/allergy/task/familyHistory/medicalHistory/
        // surgicalHistory/diagnose/assess/perform/stop_medication/
        // remove_allergy/resolve_condition were silently dropped at
        // handleInsert because `_amend_edited` was never set on those
        // branches.
        return isAmendEdit(cmd) ? { ...next, _amend_edited: true } : next;
      });
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [canEdit, wasFinalized, approved, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleDelete = useCallback((index) => {
    logEvent('DELETE_COMMAND', { index, commandType: commands[index]?.command_type });
    if (!canEdit) return;
    setCommands(prev => {
      const updated = prev.filter((_, i) => i !== index);
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [canEdit, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleAddTask = useCallback(() => {
    logEvent('ADD_TASK');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'task',
      display: '',
      data: { title: '', due_date: null, assign_to: null, labels: [] },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddOrder = useCallback(() => {
    logEvent('ADD_ORDER');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'prescribe',
      display: '',
      data: {},
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddPlan = useCallback(() => {
    logEvent('ADD_PLAN');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'plan',
      display: '',
      data: { narrative: '' },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddHistory = useCallback((commandType) => {
    logEvent('ADD_HISTORY', { type: commandType });
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: commandType,
      display: '',
      data: {},
      selected: true,
      section_key: '_history_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddMedication = useCallback(() => {
    logEvent('ADD_MEDICATION');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'medication_statement',
      display: '',
      data: { medication_text: '', fdb_code: null, sig: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddVitals = useCallback(() => {
    logEvent('ADD_VITALS');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'vitals',
      display: '',
      data: {},
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleEditRecommendation = useCallback((index, newData, newType) => {
    if (!canEdit) return;
    logEvent('EDIT_REC', { index, commandType: newType, data: newData });
    setRecommendations(prev => prev.map((cmd, i) => {
      if (i !== index) return cmd;
      const type = newType || cmd.command_type;
      if (type === 'medication_statement') {
        return { ...cmd, data: newData, display: newData.medication_text || '', accepted: true };
      }
      if (type === 'allergy') {
        return { ...cmd, data: newData, display: newData.allergy_text || '', accepted: true };
      }
      if (type === 'prescribe' || type === 'refill' || type === 'adjust_prescription') {
        return { ...cmd, command_type: type, data: newData, display: newData.medication_text || '', accepted: true };
      }
      if (type === 'refer') {
        const parts = [newData.refer_to_display, newData.clinical_question, newData.priority].filter(Boolean);
        return { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || 'Referral', accepted: true };
      }
      return { ...cmd, data: newData, accepted: true };
    }));
  }, [canEdit]);

  const handleAcceptRecommendation = useCallback((index) => {
    if (!canEdit) return;
    logEvent('ACCEPT_REC', { index });
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, accepted: true, rejected: false } : cmd
    ));
  }, [canEdit]);

  const handleRejectRecommendation = useCallback((index) => {
    if (!canEdit) return;
    logEvent('REJECT_REC', { index });
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, rejected: true, accepted: false } : cmd
    ));
  }, [canEdit]);

  const handleDeleteRecommendation = useCallback((index) => {
    if (!canEdit) return;
    logEvent('DELETE_REC', { index });
    setRecommendations(prev => prev.filter((_, i) => i !== index));
  }, [canEdit]);

  const handleEditingChange = useCallback((key, isEditing) => {
    setEditingFields(prev => {
      const next = new Set(prev);
      if (isEditing) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  const handleAddAllergy = useCallback(() => {
    logEvent('ADD_ALLERGY');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'allergy',
      display: '',
      data: { allergy_text: '', concept_id: null, concept_id_type: null, reaction: '', severity: null },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddStopMedication = useCallback(() => {
    logEvent('ADD_STOP_MED');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'stop_medication',
      display: '',
      data: { medication_id: null, medication_name: '', rationale: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddRemoveAllergy = useCallback(() => {
    logEvent('ADD_REMOVE_ALLERGY');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'remove_allergy',
      display: '',
      data: { allergy_id: null, allergy_name: '', narrative: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddResolveCondition = useCallback(() => {
    logEvent('ADD_RESOLVE_CONDITION');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'resolve_condition',
      display: '',
      data: { condition_id: null, condition_name: '', rationale: '' },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddQuestionnaire = useCallback(() => {
    logEvent('ADD_QUESTIONNAIRE');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'questionnaire',
      display: '',
      data: { questionnaire_dbid: null, questionnaire_name: '', questions: [] },
      selected: true,
      section_key: '_subjective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddCharge = useCallback(() => {
    logEvent('ADD_CHARGE');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'perform',
      display: '',
      data: { cpt_code: null, description: '', notes: '' },
      selected: true,
      section_key: '_charges_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddTemplateCharge = useCallback((cptCode, description) => {
    logEvent('ADD_TEMPLATE_CHARGE', { cptCode, description });
    if (!canEdit) return;
    setCommands(prev => {
      // Re-select if already exists but deselected. KOALA-5485: if this was
      // an amend-mode delete that the user just toggled back on, also clear
      // the `_amend_deleted` tag so handleInsert does NOT POST a delete for
      // it. The user changed their mind - no chart state change required.
      const existing = prev.find(c => c.command_type === 'perform' && c.data.cpt_code === cptCode);
      if (existing) {
        return prev.map(c => {
          if (c.command_type === 'perform' && c.data.cpt_code === cptCode) {
            const { _amend_deleted, ...rest } = c;
            return { ...rest, selected: true };
          }
          return c;
        });
      }
      return [...prev, {
        command_type: 'perform',
        display: `${cptCode} — ${description}`,
        data: { cpt_code: cptCode, description, notes: '' },
        selected: true,
        section_key: '_charges_ad_hoc',
        already_documented: false,
      }];
    });
  }, [canEdit]);

  const handleRemoveChargeByCpt = useCallback((cptCode) => {
    logEvent('REMOVE_CHARGE', { cptCode });
    if (!canEdit) return;
    // KOALA-5485: in amend mode, unchecking an already-documented charge must
    // also set `_amend_deleted: true` so handleInsert POSTs a delete to mark
    // the chart row entered-in-error. The `_amend_deleted` tag is gated by
    // `isAmendingSectionEditable` (same eligibility filter as edit) so
    // freshly-added ad-hoc charges (no command_uuid) and non-amend toggles
    // continue to behave as before - just `selected: false`.
    //
    // Without this tag the uncheck silently no-ops: handleInsert's insertable
    // filter drops the deselected command, but because no edit happened the
    // `_amend_edited` tag is never set either, so the existing amend POST
    // also drops it. Chart stays committed.
    const amending = wasFinalized && !approved;
    setCommands(prev => prev.map(c => {
      if (c.command_type !== 'perform' || c.data.cpt_code !== cptCode) return c;
      if (c.already_documented && isAmendingSectionEditable(c, amending)) {
        return { ...c, selected: false, _amend_deleted: true };
      }
      return { ...c, selected: false };
    }));
  }, [canEdit, wasFinalized, approved]);

  const handleAddCondition = useCallback((icd10Code, icd10Display, conditionId) => {
    logEvent('ADD_CONDITION', { icd10Code, display: icd10Display });
    if (!canEdit) return;
    const apKey = commands.find(c =>
      (c.command_type === 'diagnose' || c.command_type === 'assess') && ['assessment_and_plan', 'plan'].includes(c.section_key)
    )?.section_key || 'assessment_and_plan';

    const newCmd = conditionId
      ? {
          command_type: 'assess',
          display: icd10Display || '',
          data: {
            condition_id: conditionId,
            icd10_code: icd10Code || null,
            narrative: '',
            background: null,
            status: null,
          },
          section_key: apKey,
          already_documented: false,
        }
      : {
          command_type: 'diagnose',
          display: icd10Display || '',
          data: {
            icd10_code: icd10Code || null,
            icd10_display: icd10Display || '',
            condition_header: icd10Display || '',
            today_assessment: '',
            accepted: !!icd10Code,
          },
          selected: true,
          section_key: apKey,
          already_documented: false,
        };

    setCommands(prev => {
      const lastApIdx = prev.reduce((acc, c, i) =>
        (c.command_type === 'diagnose' || c.command_type === 'assess') && ['assessment_and_plan', 'plan'].includes(c.section_key) ? i : acc, -1);
      return lastApIdx === -1 ? [...prev, newCmd] : [...prev.slice(0, lastApIdx + 1), newCmd, ...prev.slice(lastApIdx + 1)];
    });

    if (icd10Code) {
      setUnmatchedConditions(prev => prev.filter(c => !(c.coding || []).some(cd => cd.code === icd10Code)));
    }

    // Carry-forward the background from the most recent prior signed assessment
    // for the same (patient, condition). Non-blocking: the user can start
    // typing immediately; the fetch may race. If it lands AFTER the user has
    // typed something, we MUST NOT overwrite their input — guard with
    // ``!c.data.background``. The /insert-commands belt is a safety net for
    // approval, but this fetch is what makes the carry-forward visible in the
    // assess edit drawer BEFORE the provider approves.
    if (conditionId) {
      fetch(`${API_BASE}/carry-forward-background`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, condition_id: conditionId }),
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data || !data.background) return;
          setCommands(prev => prev.map(c =>
            c.command_type === 'assess' && c.data.condition_id === conditionId && !c.data.background
              ? { ...c, data: { ...c.data, background: data.background } }
              : c
          ));
        })
        .catch(err => console.error('Carry-forward background fetch failed:', err));
    }
  }, [canEdit, commands, noteId]);

  const handleInsert = useCallback(async () => {
    if (!canEdit || inserting) return;
    setValidationError(null);
    logEvent('APPROVE_START', { totalCommands: commands.length, commandTypes: commands.map(c => c.command_type) });
    setInserting(true);

    // KOALA-5485: cache flip to approved=true is delayed until AFTER amend
    // success (amend branch ~1290) AND/OR AFTER /insert-commands success
    // (cache write ~1450, runs UNCONDITIONALLY on success - see
    // CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS).
    // Two cache-flip landing points cover the relevant paths:
    //   (a) Amend-only path: amend branch writes approved=true after
    //       /edit-existing-commands success and BEFORE /insert-commands. If
    //       /insert-commands later fails, the catch block rolls cache back to
    //       approved=false (so /save-summary holds the latest user-facing state).
    //   (b) Fresh-approve or amend+insert success: the success branch writes
    //       approved=true unconditionally. The unconditional write covers the
    //       amend-mode-with-zero-edits edge case (no `data.attempted` entries
    //       to gate on) and the empty-note approval crash-recovery case.
    // If a browser crash happens before either landing point, the cache stays
    // approved=false and the next page load shows pre-amend state - far safer
    // than a phantom-approved-but-lost-edit state.
    // (Original eager flip used to live here pre-amend; removed for KOALA-5485.)

    // KOALA-5485: Amend edits go through /edit-existing-commands FIRST so the
    // uuid map is available before the verify step. The frontend re-stamps
    // ScribeSummary.commands with the new uuids returned by the backend.
    //
    // Critical ordering: re-stamp happens IMMEDIATELY after amend success,
    // BEFORE the conditions fetch and /insert-commands POST. The amend POST
    // is a hard commit point - once those effects landed in home-app, the
    // plugin's local state MUST reflect it. If /insert-commands later fails,
    // the user can retry it, but they must not re-submit the (now-voided)
    // old uuid as an amend - which is what would happen if we kept the
    // re-stamp inside the /insert-commands success branch.
    const amendEdits = commands.filter(c => c._amend_edited && c.command_uuid);
    // KOALA-5485 charge-delete regression: unchecking an already-documented
    // perform command sets `_amend_deleted` (see handleRemoveChargeByCpt).
    // Send these to /delete-existing-commands BEFORE the edit POST so that:
    //  - The delete is a hard commit point of its own (EIE landed in home-app).
    //  - The frontend removes them from `workingCommands` so /insert-commands
    //    never sees them and /edit-existing-commands never tries to edit
    //    them either (they should not have `_amend_edited` set; the gate is
    //    structural - delete vs edit are mutually exclusive gestures).
    const amendDeletes = commands.filter(c => c._amend_deleted && c.command_uuid && c.already_documented);
    let amendUuidRemap = new Map(); // old_uuid -> new_uuid
    let amendAttempted = [];
    // The commands array we work with from here on. We mutate this in-place
    // (via reassign) to reflect amend success even if /insert-commands fails.
    let workingCommands = commands;
    if (amendDeletes.length > 0) {
      const deletePayload = amendDeletes.map(({ _template_inserted, _amend_edited, _amend_deleted, ...rest }) => rest);
      logEvent('AMEND_DELETE_SENDING', { count: deletePayload.length, sectionKeys: deletePayload.map(c => c.section_key) });
      try {
        const delRes = await fetch(`${API_BASE}/delete-existing-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, commands: deletePayload }),
        });
        const delData = await delRes.json();
        if (delData.error) {
          if (delData.validation_errors) {
            setValidationError(delData.validation_errors);
          } else if (delData.conflicts) {
            setError(`${delData.error}. Reload the page to see the latest state.`);
          } else {
            setError(delData.error);
          }
          setApproved(false);
          setConfirming(false);
          saveSummaryToCache(noteData, commands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
          setInserting(false);
          logEvent('AMEND_DELETE_ERROR', { error: delData.error, conflicts: delData.conflicts || null });
          return;
        }
        logEvent('AMEND_DELETE_COMPLETE', { count: (delData.attempted || []).length });
        // Hard commit point: the deleted commands' chart rows are now
        // entered_in_error. Filter them out of workingCommands so they
        // don't appear in subsequent POSTs (edit, insert) or in the
        // cache write. The next page load will not see them in cache;
        // home-app already considers them voided.
        const deletedUuids = new Set(amendDeletes.map(c => c.command_uuid));
        workingCommands = commands.filter(c => !(c.command_uuid && deletedUuids.has(c.command_uuid)));
        setCommands(workingCommands);
        saveSummaryToCache(noteData, workingCommands, true, {
          recommendations, unmatched_conditions: unmatchedConditions,
          diagnosis_suggestions: diagnosisSuggestions,
          selected_template_name: selectedTemplate?.name || null, mode,
        });
      } catch (err) {
        console.error('Amend deletes failed:', err);
        setError('Failed to apply amendment deletes');
        setApproved(false);
        setConfirming(false);
        setInserting(false);
        logEvent('AMEND_DELETE_ERROR', { error: 'network' });
        return;
      }
    }
    if (amendEdits.length > 0) {
      const amendPayload = amendEdits.map(({ _template_inserted, _amend_edited, ...rest }) => rest);
      logEvent('AMEND_EDIT_SENDING', { count: amendPayload.length, sectionKeys: amendPayload.map(c => c.section_key) });
      try {
        const editRes = await fetch(`${API_BASE}/edit-existing-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, commands: amendPayload }),
        });
        const editData = await editRes.json();
        if (editData.error) {
          // Backend rejected before any effects were emitted. Pass the
          // conflict shape through if present so the user can reload a
          // stale tab; otherwise show the generic error.
          if (editData.validation_errors) {
            setValidationError(editData.validation_errors);
          } else if (editData.conflicts) {
            setError(`${editData.error}. Reload the page to see the latest state.`);
          } else {
            setError(editData.error);
          }
          setApproved(false);
          setConfirming(false);
          saveSummaryToCache(noteData, commands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
          setInserting(false);
          logEvent('AMEND_EDIT_ERROR', { error: editData.error, conflicts: editData.conflicts || null });
          return;
        }
        amendAttempted = editData.attempted || [];
        for (const entry of amendAttempted) {
          amendUuidRemap.set(entry.old_command_uuid, entry.new_command_uuid);
        }
        logEvent('AMEND_EDIT_COMPLETE', { count: amendAttempted.length });

        // Hard commit point: re-stamp commands now. After this point the
        // home-app has executed EIE+Originate (and Commit for dedicated-class
        // sections). The local state must mirror that or a retry of
        // /insert-commands will resend the (now-voided) old uuid as an amend.
        //
        // KOALA-5485: map over `workingCommands` (NOT the original `commands`)
        // so that deleted commands (filtered out by the delete branch above)
        // don't re-appear here. Mapping over the original would re-introduce
        // them with their old uuid - and they'd then go through the insertable
        // filter (which drops them on `already_documented` anyway, so no chart
        // damage), but the cache write below would persist them.
        workingCommands = workingCommands.map(cmd => {
          if (cmd._amend_edited && cmd.command_uuid && amendUuidRemap.has(cmd.command_uuid)) {
            const newUuid = amendUuidRemap.get(cmd.command_uuid);
            const { _amend_edited, ...rest } = cmd;
            return { ...rest, command_uuid: newUuid, already_documented: true };
          }
          return cmd;
        });
        setCommands(workingCommands);
        saveSummaryToCache(noteData, workingCommands, true, {
          recommendations, unmatched_conditions: unmatchedConditions,
          diagnosis_suggestions: diagnosisSuggestions,
          selected_template_name: selectedTemplate?.name || null, mode,
        });
      } catch (err) {
        console.error('Amend edits failed:', err);
        setError('Failed to apply amendment edits');
        setApproved(false);
        setConfirming(false);
        setInserting(false);
        logEvent('AMEND_EDIT_ERROR', { error: 'network' });
        return;
      }
    }

    const SECTION_TYPES = new Set(['physical_exam', 'ros', 'chart_review', 'history_review']);
    const insertable = workingCommands.filter(c => {
      // Either flag means "already on the note." command_uuid is the
      // authoritative signal (set whenever a command is inserted, whether
      // via full Approve or Add Now). already_documented is the explicit
      // marker. Treat either as exclusionary so pre-existing finalized
      // notes (which have UUIDs but no already_documented flag) don't
      // double-insert on amendment re-Approve.
      // (Amend-edited commands have been re-stamped above with the new
      // uuid + already_documented=true, so they naturally filter out here.)
      if (c.already_documented || c.command_uuid) return false;
      if (!c.display && !(SECTION_TYPES.has(c.command_type) && c.data?.sections?.length > 0)) return false;
      if (c.command_type === 'imaging_order' && (!c.data.image_code || !c.data.service_provider || !c.data.ordering_provider_id || !c.data.diagnosis_codes || c.data.diagnosis_codes.length === 0)) return false;
      if (c.command_type === 'prescribe' && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null)) return false;
      if ((c.command_type === 'refill' || c.command_type === 'adjust_prescription') && !c.data.fdb_code) return false;
      if (c.command_type === 'lab_order' && (!c.data.lab_partner || !c.data.tests_order_codes || c.data.tests_order_codes.length === 0)) return false;
      if (c.command_type === 'refer' && (!c.data.service_provider || !c.data.clinical_question || !c.data.notes_to_specialist || !c.data.diagnosis_codes || c.data.diagnosis_codes.length === 0)) return false;
      if (c.command_type === 'perform' && (!c.data.cpt_code || c.selected === false)) return false;
      return true;
    });
    const dropped = workingCommands.filter(c => !c.already_documented && !insertable.includes(c));
    if (dropped.length > 0) {
      logEvent('COMMANDS_FILTERED', { dropped: dropped.map(c => ({
        type: c.command_type, display: (c.display || '').slice(0, 80), sectionKey: c.section_key,
        reason: !c.display ? 'empty_display' : c.selected === false ? 'deselected' : 'validation',
      })) });
    }
    const acceptedRecs = recommendations.filter(c => c.accepted && !c.already_documented && c.display);
    let allInsertable = [...insertable, ...acceptedRecs]
      .map(({ _template_inserted, ...c }) => c); // Strip internal marker.

    // Convert diagnose commands: match against patient conditions to decide assess vs diagnose.
    // Skip diagnose commands with no ICD code (provider didn't select one).
    try {
      const condRes = await fetch(
        `${API_BASE}/patient-conditions?patient_id=${encodeURIComponent(patientId)}`
      );
      const condData = await condRes.json();
      const patientConditions = condData.conditions || [];

      allInsertable = allInsertable
        .filter(c => c.command_type !== 'diagnose' || (c.data.icd10_code && c.data.accepted))
        .map(c => {
          if (c.command_type !== 'diagnose') return c;
          const code = (c.data.icd10_code || '').replace('.', '').toUpperCase();
          const match = patientConditions.find(pc => {
            const pcCode = (pc.code || '').replace('.', '').toUpperCase();
            return pcCode === code;
          });
          if (match) {
            return {
              ...c,
              command_type: 'assess',
              data: {
                condition_id: match.condition_id,
                narrative: c.data.today_assessment || '',
                background: c.data.background || null,
                status: null,
              },
            };
          }
          return c;
        });
    } catch (err) {
      console.error('Failed to fetch patient conditions for assess check:', err);
    }
    // Prescriptions first so they appear at the top of the note.
    const RX_SET = new Set(['prescribe', 'refill', 'adjust_prescription']);
    allInsertable.sort((a, b) => (RX_SET.has(a.command_type) ? 0 : 1) - (RX_SET.has(b.command_type) ? 0 : 1));
    logEvent('COMMANDS_SENDING', { commands: allInsertable.map(c => ({
      type: c.command_type, display: (c.display || '').slice(0, 80), sectionKey: c.section_key,
    })) });
    try {
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: allInsertable }),
      });
      const data = await res.json();
      if (data.error) {
        // If amend already succeeded, the home-app already executed those
        // EIE+Originate effects. We persist `workingCommands` (which carries
        // the re-stamped uuids) so a retry of /insert-commands won't re-send
        // the now-voided old uuid as an amend. The `approved` flag is reset
        // so the user can fix the insert-commands payload and retry.
        if (data.validation_errors) {
          setValidationError(data.validation_errors);
        } else if (amendAttempted.length > 0) {
          setError(`${data.error}. Amendments were saved; retry to complete insertion.`);
        } else {
          setError(data.error);
        }
        setApproved(false);
        setConfirming(false);
        saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
        logEvent('APPROVE_ERROR', { error: data.error, validation_errors: data.validation_errors, amendAttempted: amendAttempted.length });
      } else {
        // Phase 2: Insert metadata if any pending
        if (data.metadata_pending && data.metadata_pending.length > 0) {
          try {
            await fetch(`${API_BASE}/insert-metadata`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ note_uuid: noteId, pending: data.metadata_pending }),
            });
          } catch (metaErr) {
            console.error('Failed to insert metadata:', metaErr);
          }
        }
        // Stamp commands with their UUIDs and save immediately (before modal closes).
        // Amend re-stamping happened earlier (right after /edit-existing-commands
        // succeeded); here we only re-stamp the freshly-inserted commands.
        let updatedCommands = workingCommands;
        if (data.attempted && data.attempted.length > 0) {
          const uuidMap = new Map((data.attempted || []).map(a => [`${a.command_type}:${a.display}`, a.command_uuid]));
          updatedCommands = workingCommands.map(cmd => {
            const key = `${cmd.command_type}:${(cmd.display || '').slice(0, 80)}`;
            const uuid = uuidMap.get(key);
            // Stamp already_documented=true alongside command_uuid so the existing
            // `insertable` filter naturally excludes these commands on re-Approve
            // during amendment. Today's flow only sets already_documented from the
            // Add Now path; the full-Approve path skipped it, which would have
            // caused double-insertion on re-Approve. (KOALA-5485)
            return uuid ? { ...cmd, command_uuid: uuid, already_documented: true } : cmd;
          });
          setCommands(updatedCommands);
        }
        // CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS - KOALA-5485 cache-flip regression:
        // the approved=true cache write must fire UNCONDITIONALLY on the success branch,
        // NOT gated on `data.attempted.length > 0`. Two paths reach here with zero
        // attempted entries:
        //   (1) Amend-mode Save with zero edits in any editable section - the amend
        //       branch already cached approved=true at line ~1294, but if there are
        //       NO amend edits at all (empty-note approval), neither branch wrote
        //       approved=true to cache. Without this unconditional write, setApproved(true)
        //       updates React state in memory but the cache holds approved=false;
        //       a page reload would revert the UI to pre-approval.
        //   (2) Fresh approval crash-recovery: if the user crashes before this
        //       point with a successful insert but empty attempted (rare but possible
        //       for command types that don't surface attempted entries), the cache
        //       must reflect approved=true so reload doesn't lose the approval.
        // Pinned by `test_summary_js_cache_flip_to_approved_true_is_unconditional_on_success`.
        saveSummaryToCache(noteData, updatedCommands, true, {
          recommendations, unmatched_conditions: unmatchedConditions,
          diagnosis_suggestions: diagnosisSuggestions,
          selected_template_name: selectedTemplate?.name || null, mode,
        });
        const hasPrescriptions = workingCommands.some(c => c.display && RX_SET.has(c.command_type))
          || recommendations.some(c => c.display && !c.rejected && RX_SET.has(c.command_type));
        logEvent('APPROVE_COMPLETE', { insertedCount: allInsertable.length, effectCount: data.inserted, hasPendingMetadata: (data.metadata_pending?.length || 0) > 0, amendEditCount: amendAttempted.length });
        // Verify commands were actually created (include Add Now items + amend-edit NEW uuids).
        const amendVerifyEntries = amendAttempted.map(a => ({
          command_uuid: a.new_command_uuid,
          command_type: a.command_type,
          display: a.display || '',
        }));
        const allAttempted = [...addNowAttemptedRef.current, ...(data.attempted || []), ...amendVerifyEntries];
        if (allAttempted.length > 0) {
          try {
            const verifyRes = await fetch(`${API_BASE}/verify-commands`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ note_uuid: noteId, attempted: allAttempted }),
            });
            const verifyData = await verifyRes.json();
            const failedCount = verifyData.failed?.length || 0;
            const verifiedCount = verifyData.verified?.length || 0;
            const vResult = failedCount > 0
              ? { ok: false, verified: verifyData.verified || [], failed: verifyData.failed }
              : { ok: true, verified: verifyData.verified || [], failed: [] };
            setVerificationResult(vResult);
            if (failedCount > 0) {
              logEvent('COMMANDS_FAILED', { failed: verifyData.failed });
            } else {
              logEvent('COMMANDS_VERIFIED', { total: verifiedCount });
            }
          } catch (verifyErr) {
            console.error('Verification failed:', verifyErr);
          }
        }
        setApproved(true);
        // if (!hasPrescriptions) {
        //   try {
        //     await fetch(`${API_BASE}/sign-note`, {
        //       method: 'POST',
        //       headers: { 'Content-Type': 'application/json' },
        //       body: JSON.stringify({ note_uuid: noteId }),
        //     });
        //     logEvent('NOTE_SIGNED');
        //   } catch (signErr) {
        //     console.error('Failed to sign note:', signErr);
        //   }
        // }
        const port = window.__canvasPort && window.__canvasPort();
        if (port) port.postMessage({ type: 'CLOSE_MODAL' });
      }
    } catch (err) {
      // Network/parsing failure on /insert-commands. If amend already
      // succeeded we persist the re-stamped state so retry doesn't
      // re-submit voided uuids as amends.
      if (amendAttempted.length > 0) {
        setError('Amendments saved; some commands failed to insert. Retry.');
      } else {
        setError('Failed to insert commands');
      }
      setApproved(false);
      setConfirming(false);
      saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
      logEvent('APPROVE_ERROR', { error: 'Failed to insert commands', amendAttempted: amendAttempted.length });
    } finally {
      setInserting(false);
    }
  }, [commands, recommendations, noteId, noteData, saveSummaryToCache, unmatchedConditions, diagnosisSuggestions, canEdit, inserting]);

  const handleAddNow = useCallback(async (command, isRecommendation, index) => {
    if (!canEdit) return;
    logEvent('ADD_NOW', { commandType: command.command_type, isRecommendation, index });
    // Mark as adding to show spinner and prevent double-clicks.
    const setAdding = (flag) => {
      if (isRecommendation) {
        setRecommendations(prev => prev.map((rec, i) => i === index ? { ...rec, _adding: flag } : rec));
      } else {
        setCommands(prev => prev.map((cmd, i) => i === index ? { ...cmd, _adding: flag } : cmd));
      }
    };
    setAdding(true);
    try {
      const { _template_inserted, ...payload } = command;
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: [payload] }),
      });
      const data = await res.json();
      if (data.error) { setAdding(false); logEvent('ADD_NOW_ERROR', { commandType: command.command_type, index }); return; }
      // Phase 2: insert metadata if needed (e.g. alert_facility).
      if (data.metadata_pending && data.metadata_pending.length > 0) {
        try {
          await fetch(`${API_BASE}/insert-metadata`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note_uuid: noteId, pending: data.metadata_pending }),
          });
        } catch (metaErr) { console.error('Add Now metadata failed:', metaErr); }
      }
      // Track attempted entry for verification merge with Approve All.
      const attemptedEntry = data.attempted && data.attempted[0];
      if (attemptedEntry) {
        addNowAttemptedRef.current.push(attemptedEntry);
      }
      if (isRecommendation) {
        setRecommendations(prev => prev.map((rec, i) =>
          i === index ? { ...rec, already_documented: true, accepted: true, _added_now: true, _adding: false, command_uuid: attemptedEntry?.command_uuid || null } : rec
        ));
      } else {
        setCommands(prev => prev.map((cmd, i) =>
          i === index ? { ...cmd, already_documented: true, _added_now: true, _adding: false, command_uuid: attemptedEntry?.command_uuid || null } : cmd
        ));
      }
      logEvent('ADD_NOW_SUCCESS', { commandType: command.command_type, index });
    } catch (err) {
      console.error('Add Now failed:', err);
      setAdding(false);
      logEvent('ADD_NOW_ERROR', { commandType: command.command_type, index });
    }
  }, [noteId, canEdit]);


  const commandBySectionKey = buildCommandBySectionKey(commands);
  const adHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_ad_hoc');
  const objectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_objective_ad_hoc');
  const historyAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_history_ad_hoc');
  const subjectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_subjective_ad_hoc');
  const chargeAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_charges_ad_hoc');

  const insertableCount = commands.filter(c => {
    if (c.command_type === 'diagnose') return c.data.icd10_code && c.data.accepted && c.display;
    return !c.already_documented && c.display;
  }).length
    + recommendations.filter(c => c.accepted && !c.already_documented && c.display).length;
  const RX_TYPES = new Set(['prescribe', 'refill', 'adjust_prescription']);
  const hasRxCommands = commands.some(c => c.display && RX_TYPES.has(c.command_type))
    || recommendations.some(c => c.display && !c.rejected && RX_TYPES.has(c.command_type));
  // Accept and Sign is only offered once the user has committed to a flow
  // and reached its natural completion point. Manual mode shows it as soon
  // as the user opts in (so they can sign with empty / template-only fields
  // if that's what they want). AI mode requires recording to be finalized
  // AND the note to have been generated — we don't want a half-finished
  // transcript or an in-flight LLM call to be signable.
  const aiFlowComplete = mode === 'ai' && recording.finalized && noteData !== null;
  const showFooter = canEdit && (mode === 'manual' || aiFlowComplete);

  const INCOMPLETE_LABELS = { diagnose: 'diagnose', imaging_order: 'imaging order', prescribe: 'prescription', refer: 'referral', lab_order: 'lab order' };
  const _isRxIncomplete = (d) => !d.fdb_code || !d.sig || d.quantity_to_dispense == null || !d.type_to_dispense || d.refills == null;
  const _isLabIncomplete = (d) => !d.lab_partner || !d.tests_order_codes || d.tests_order_codes.length === 0;
  const _isImagingIncomplete = (d) => !d.image_code || !d.service_provider || !d.ordering_provider_id || !d.diagnosis_codes || d.diagnosis_codes.length === 0;
  const _isReferIncomplete = (d) => !d.service_provider || !d.clinical_question || !d.notes_to_specialist || !d.diagnosis_codes || d.diagnosis_codes.length === 0;
  const incompleteTypes = [];
  for (const c of commands) {
    if (c.already_documented) continue;
    if (c.command_type === 'imaging_order' && c.display && _isImagingIncomplete(c.data)) {
      if (!incompleteTypes.includes('imaging_order')) incompleteTypes.push('imaging_order');
    }
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && c.display && _isRxIncomplete(c.data)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
    if (c.command_type === 'lab_order' && c.display && _isLabIncomplete(c.data)) {
      if (!incompleteTypes.includes('lab_order')) incompleteTypes.push('lab_order');
    }
    if (c.command_type === 'refer' && c.display && _isReferIncomplete(c.data)) {
      if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
    }
  }
  for (const c of recommendations) {
    if (c.already_documented || !c.display || c.rejected) continue;
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
    if (c.command_type === 'refer' && _isReferIncomplete(c.data)) {
      if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
    }
  }
  const incompleteCount = commands.filter(c =>
    !c.already_documented && c.display && (
      (c.command_type === 'imaging_order' && _isImagingIncomplete(c.data)) ||
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) ||
      (c.command_type === 'lab_order' && _isLabIncomplete(c.data)) ||
      (c.command_type === 'refer' && _isReferIncomplete(c.data))
    )
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && !c.rejected && (
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) ||
      (c.command_type === 'refer' && _isReferIncomplete(c.data))
    )
  ).length;
  const UNDECIDED_LABELS = { diagnose: 'diagnosis', medication_statement: 'medication', allergy: 'allergy', prescribe: 'prescription', refill: 'prescription', adjust_prescription: 'prescription', refer: 'referral' };
  const undecidedTypes = [];
  for (const c of commands) {
    if (!c.already_documented && c.display && c.command_type === 'diagnose' && !c.data.accepted && !c.data.rejected) {
      if (!undecidedTypes.includes(c.command_type)) undecidedTypes.push(c.command_type);
    }
  }
  for (const c of recommendations) {
    if (!c.already_documented && c.display && !c.accepted && !c.rejected) {
      if (!undecidedTypes.includes(c.command_type)) undecidedTypes.push(c.command_type);
    }
  }
  const undecidedRecommendationCount = commands.filter(c =>
    !c.already_documented && c.display && c.command_type === 'diagnose' && !c.data.accepted && !c.data.rejected
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && !c.accepted && !c.rejected
  ).length;
  const hasUnsavedEdits = editingFields.size > 0;

  // Ensure sections with ad-hoc buttons are always present even if Nabla omits them.
  const ENSURE_KEYS = new Map([
    ['vitals', { key: 'vitals', title: 'Vitals', text: '' }],
    ['current_medications', { key: 'current_medications', title: 'Meds Discussed', text: '' }],
    ['allergies', { key: 'allergies', title: 'Allergies Discussed', text: '' }],
    ['past_medical_history', { key: 'past_medical_history', title: 'Past Medical History', text: '' }],
    ['past_surgical_history', { key: 'past_surgical_history', title: 'Past Surgical History', text: '' }],
    ['family_history', { key: 'family_history', title: 'Family History', text: '' }],
    ['lab_results', { key: 'lab_results', title: 'Lab Results', text: '' }],
    ['imaging_results', { key: 'imaging_results', title: 'Imaging Results', text: '' }],
    ['physical_exam', { key: 'physical_exam', title: 'Physical Exam', text: '' }],
  ]);
  const effectiveSections = (() => {
    const base = noteData ? noteData.sections : SKELETON_SECTIONS;
    const existing = new Set(base.map(s => s.key.toLowerCase()));
    const missing = [...ENSURE_KEYS.entries()].filter(([k]) => !existing.has(k)).map(([, v]) => v);
    return missing.length > 0 ? [...base, ...missing] : base;
  })();
  const isRecording = recording.status === 'recording' || recording.status === 'paused';
  // Suppress "Recording in progress" / "Paused" labels (and the recording dot)
  // once a note has been generated or the transcript was finalized — at that
  // point the transcript is a static record, not a live capture.
  const transcriptHeaderIsLive = isRecording && !noteData && !recording.finalized;
  const showTopControls = canEdit && !noteData && !isRecording && !recording.finalized && !generating && mode === null;

  // Unified progress display: "Finalizing transcript" is step 0 of a sequence
  // that continues through the server-driven generate pipeline. Showing one
  // bar that ticks across all 6 steps gives the user a clear sense of motion
  // during the speaker-attribution wait + LLM run rather than a long stretch
  // of dead "Finalizing..." text followed by a separate progress bar.
  const isFinalizing = recording.status === 'finishing';
  const isInGenerationPipeline = generating || (recording.finalized && mode === 'ai' && !noteData);
  const showProgressBanner = isFinalizing || isInGenerationPipeline;
  let progressIndex = 0;
  let progressLabel = FINALIZE_LABEL;
  if (!isFinalizing && isInGenerationPipeline) {
    const serverStep = Math.max(progress.step, 0);
    progressIndex = serverStep + 1; // +1 because finalize occupies index 0
    progressLabel = PROGRESS_STEPS[serverStep] || PROGRESS_STEPS[0];
  }
  const progressPct = Math.max(((progressIndex + 1) / TOTAL_PROGRESS_STEPS) * 100, 5);

  return html`
    <div class=${`summary-container${!canEdit && !approved ? ' summary-container--readonly' : ''}`}>
      ${isAuthor && isNoteEditable && wasFinalized && html`
        <div class=${`summary-status-pill summary-status-pill--${approved ? 'finalized' : 'amending'}`} role="status" aria-live="polite">
          <svg class="summary-status-pill-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            ${approved
              ? html`<polyline points="20 6 9 17 4 12"/>`
              : html`<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>`
            }
          </svg>
          <span class="summary-status-pill-text">
            ${approved ? 'Charting finalized' : 'Editing charting'}
          </span>
          ${approved && html`
            <button class="summary-status-pill-btn" onClick=${handleMakeChanges}>
              Make changes
            </button>
          `}
        </div>
      `}
      ${readOnlyReason === 'locked' && html`
        <div class="readonly-banner" role="status" aria-live="polite">
          <svg class="readonly-banner-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>Scribe documentation is incomplete. Click <strong>Amend</strong> in the note footer to finish.</span>
        </div>
      `}
      ${readOnlyReason === 'non_author' && html`
        <div class="readonly-banner" role="status" aria-live="polite">
          <svg class="readonly-banner-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>Read-only — only the note author can edit the Scribe tab.</span>
        </div>
      `}
      ${canEdit && html`
        <div class="unified-top-bar">
          ${templates.length > 0 && html`
            <select
              class="template-select"
              onChange=${handleSelectTemplate}
              value=${selectedTemplate ? selectedTemplate.name : ''}
              disabled=${approved || generating || noteData !== null || mode !== null}
            >
              <option value="">Select Visit Type</option>
              ${templates.map(t => html`<option key=${t.name} value=${t.name}>${t.name}</option>`)}
            </select>
          `}
          ${showTopControls && html`
            <button class="start-ai-btn" onClick=${handleStartAI} disabled=${!selectedTemplate}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8" /></svg>
              Start AI Scribe
            </button>
            <button class="start-manual-btn" onClick=${handleStartManual} disabled=${!selectedTemplate}>
              Manual
            </button>
          `}
          ${isRecording && html`
            <div class="recording-controls-inline">
              ${recording.status === 'recording'
                ? html`<button class="control-btn" onClick=${recording.pauseRecording} title="Pause">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="5" width="4" height="14" rx="1" />
                      <rect x="14" y="5" width="4" height="14" rx="1" />
                    </svg>
                    Pause
                  </button>`
                : html`<button class="control-btn" onClick=${recording.resumeRecording} title="Resume">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="6,4 20,12 6,20" />
                    </svg>
                    Resume
                  </button>`}
              <${FinishRecordingButton} onFinish=${recording.finishRecording} />
            </div>
          `}
          ${false && debugMode && noteData && !approved && !generating && !isRecording && html`
            <button class="regenerate-btn" onClick=${handleGenerate} disabled=${!selectedTemplate}>
              Regenerate${!selectedTemplate ? ' (select visit type)' : ''}
            </button>
          `}
        </div>
      `}
      ${(isRecording || recording.entries.length > 0) && html`
        <div class="transcript-panel">
          <button class="transcript-panel-header ${transcriptHeaderIsLive ? '' : 'finalized'}" onClick=${() => setTranscriptCollapsed(prev => !prev)}>
            <div class="transcript-panel-status ${transcriptHeaderIsLive ? '' : 'finalized'}">
              ${transcriptHeaderIsLive && recording.status === 'recording' && html`
                <span class="recording-dot recording-dot-live"
                  style=${{
                    transform: `scale(${1 + Math.min(recording.audioLevel * 8, 1)})`,
                    opacity: 0.6 + Math.min(recording.audioLevel * 6, 0.4),
                  }}
                ></span>
              `}
              ${transcriptHeaderIsLive && recording.status === 'paused' && html`<span class="recording-dot recording-dot-paused"></span>`}
              <span>${transcriptHeaderIsLive
                ? (recording.status === 'paused' ? 'Paused' : 'Recording in progress')
                : 'Transcript'}</span>
              ${!transcriptHeaderIsLive && html`<span class="transcript-entry-count">(${recording.entries.filter(e => e.is_final).length})</span>`}
            </div>
            <span class="transcript-panel-toggle">${transcriptCollapsed ? 'Show' : 'Hide'}</span>
          </button>
          ${showSavedToast && html`<div class="transcript-saved-toast">Transcript saved</div>`}
          ${!transcriptCollapsed && html`
            <div class="transcript-panel-body" ref=${transcriptBodyRef}>
              ${recording.entries.length > 0
                ? html`
                  <div class="transcript-list">
                    ${recording.entries.map((entry, i) => html`
                      <${TranscriptEntry}
                        key=${entry.item_id || i}
                        ...${entry}
                        providerName=${providerName}
                        providerPhotoUrl=${providerPhotoUrl}
                        patientName=${patientName}
                      />
                    `)}
                  </div>
                `
                : html`<p class="transcript-placeholder">Transcript will appear here as you speak...</p>`}
            </div>
          `}
        </div>
      `}
      ${recording.micPrompting && html`
        <div class="mic-prompting-banner">
          <div class="mic-prompting-spinner" />
          <span>Waiting for microphone permission…</span>
        </div>
      `}
      ${recording.micBlocked && html`
        <div class="mic-blocked-banner">
          <div class="mic-blocked-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="#c0392b">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              <line x1="3" y1="3" x2="21" y2="21" stroke="#c0392b" stroke-width="2"/>
            </svg>
          </div>
          <div class="mic-blocked-content">
            <strong>Microphone Access Blocked</strong>
            <p>Microphone permission is required to record. Tap the button below to allow access.</p>
          </div>
          <div class="mic-blocked-actions">
            <button class="mic-blocked-btn mic-blocked-btn-refresh" onClick=${() => recording.retryMicPermission()}>Enable Microphone</button>
          </div>
        </div>
      `}
      ${recording.connectionLost && recording.status === 'recording' && html`
        <div class="connection-lost-warning">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;">
            <path d="M24 8.98C20.93 5.9 16.69 4 12 4S3.07 5.9 0 8.98L12 21 24 8.98zM2.92 9.07C5.51 7.08 8.67 6 12 6s6.49 1.08 9.08 3.07l-1.43 1.43C17.5 8.94 14.86 8 12 8s-5.5.94-7.65 2.51L2.92 9.07zM12 18l-6.22-6.22C7.84 10.14 9.82 9.25 12 9.25s4.16.89 6.22 2.53L12 18z"/>
            <line x1="4" y1="4" x2="20" y2="20" stroke="currentColor" stroke-width="2"/>
          </svg>
          Connection lost — reconnecting. Audio is being buffered locally.
        </div>
      `}
      ${recording.silenceWarning && recording.status === 'recording' && html`
        <div class="silence-warning">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
          No audio detected — check your microphone permissions and make sure it is not muted
        </div>
      `}
      ${recording.error && html`<p class="error" style="padding: 0 16px;">${recording.error}</p>`}
      ${showProgressBanner && html`
        <div class="summary-generating-banner">
          <div class="generating-bar" style="width: ${progressPct}%" />
          <span class="generating-label">${progressLabel}...</span>
        </div>
      `}
      ${canEdit && !noteData && !generating && recording.finalized && mode === 'ai' && html`
        <div class="summary-generate-banner">
          <p class="summary-banner-description">Recording complete. Generate a structured summary from your transcript.</p>
          <button class="generate-btn" onClick=${handleGenerate}>Generate Summary</button>
        </div>
      `}
      ${error && html`<p class="error" style="padding: 0 16px;">${error}</p>`}
      ${canEdit && recommendations.length > 0 && html`
        <div class="hide-rejected-toggle">
          <label class="hide-rejected-label" onClick=${() => setHideRejected(prev => !prev)}>
            <div class="toggle-switch${hideRejected ? ' on' : ''}">
              <div class="toggle-knob" />
            </div>
            Hide Rejected Recommendations
          </label>
        </div>
      `}
      <div class=${`summary-body${inserting ? ' summary-body--inserting' : ''}`}>
        ${renderSoapGroups(effectiveSections, commandBySectionKey, handleEdit, handleDelete, {
          adHocCommands,
          objectiveAdHocCommands,
          historyAdHocCommands,
          subjectiveAdHocCommands,
          chargeAdHocCommands,
          assignees,
          onAddTask: canEdit ? handleAddTask : null,
          onAddOrder: canEdit ? handleAddOrder : null,
          onAddPlan: canEdit ? handleAddPlan : null,
          onAddVitals: canEdit ? handleAddVitals : null,
          onAddMedication: canEdit ? handleAddMedication : null,
          onAddAllergy: canEdit ? handleAddAllergy : null,
          onAddStopMedication: canEdit ? handleAddStopMedication : null,
          onAddRemoveAllergy: canEdit ? handleAddRemoveAllergy : null,
          onAddResolveCondition: canEdit ? handleAddResolveCondition : null,
          onAddHistory: canEdit ? handleAddHistory : null,
          onAddQuestionnaire: canEdit ? handleAddQuestionnaire : null,
          onAddCharge: canEdit ? handleAddCharge : null,
          onAddTemplateCharge: canEdit ? handleAddTemplateCharge : null,
          onRemoveChargeByCpt: canEdit ? handleRemoveChargeByCpt : null,
          templateCharges: selectedTemplate ? (selectedTemplate.charges || []) : [],
          readOnly: !canEdit,
          isAmending: wasFinalized && !approved,
          sectionConditions,
          patientId,
          noteId,
          staffId,
          staffName,
          recommendations,
          onEditRecommendation: handleEditRecommendation,
          onDeleteRecommendation: handleDeleteRecommendation,
          onAcceptRecommendation: handleAcceptRecommendation,
          onRejectRecommendation: handleRejectRecommendation,
          onAddCondition: canEdit ? handleAddCondition : null,
          unmatchedConditions,
          diagnosisSuggestions,
          onAddNow: (canEdit && !(wasFinalized && !approved)) ? handleAddNow : null,
          hideRejected,
          alertFacilityEnabled,
          onEditingChange: handleEditingChange,
          questionnaireScores: collectQuestionnaireScores(commands),
        })}
      </div>
      ${verificationResult && html`<${VerificationSummary} result=${verificationResult} />`}
      ${validationError && html`
        <div class="validation-error">
          <strong>Please fix before approving:</strong>
          <ul>
            ${(Array.isArray(validationError) ? validationError : [{ display: '', errors: [validationError] }]).map(v => html`
              ${v.errors.map(e => html`<li key=${e}><strong>${v.display || v.command_type}</strong>: ${e}</li>`)}
            `)}
          </ul>
        </div>
      `}
      ${showFooter && html`
        <div class="summary-footer">
          ${inserting ? html`
            <div class="approve-progress">
              <div class="approve-spinner" />
              <span>Inserting ${insertableCount} ${insertableCount === 1 ? 'command' : 'commands'} into note...</span>
            </div>
          ` : confirming ? html`
            <div class="approve-confirm-block">
              ${hasUnsavedEdits && html`
                <div class="summary-footer-warning">
                  ${editingFields.size} unsaved ${editingFields.size === 1 ? 'edit' : 'edits'} \u2014 save or cancel to continue.
                </div>
              `}
              <button class="insert-btn confirm" disabled=${hasUnsavedEdits} onClick=${handleInsert}>${wasFinalized ? (hasRxCommands ? 'Confirm: Save changes and review prescriptions' : 'Confirm: Save changes') : (hasRxCommands ? 'Confirm: Accept and review prescriptions' : 'Confirm: Accept and sign')}</button>
              <button class="approve-cancel" onClick=${() => setConfirming(false)}>Cancel</button>
            </div>
          ` : html`
            <div class="approve-block">
              ${incompleteCount > 0 && html`
                <div class="summary-footer-warning">
                  ${incompleteCount} incomplete ${incompleteCount === 1 ? 'item' : 'items'} will be skipped: ${incompleteTypes.map(t => INCOMPLETE_LABELS[t]).join(', ')}
                </div>
              `}
              ${undecidedRecommendationCount > 0 && html`
                <div class="summary-footer-warning">
                  ${undecidedRecommendationCount} ${undecidedRecommendationCount === 1 ? 'recommendation needs' : 'recommendations need'} a decision, ${undecidedRecommendationCount === 1 ? 'it has' : 'they have'} not been accepted nor rejected: ${undecidedTypes.map(t => UNDECIDED_LABELS[t] || t).join(', ')}
                </div>
              `}
              ${hasUnsavedEdits && html`
                <div class="summary-footer-warning">
                  ${editingFields.size} unsaved ${editingFields.size === 1 ? 'edit' : 'edits'} \u2014 save or cancel to continue.
                </div>
              `}
              <button class="insert-btn" disabled=${undecidedRecommendationCount > 0 || hasUnsavedEdits} onClick=${() => setConfirming(true)}>${wasFinalized ? (hasRxCommands ? 'Save changes and review prescriptions' : 'Save changes') : (hasRxCommands ? 'Accept and review prescriptions' : 'Accept and sign')}</button>
              ${!wasFinalized && html`<div class="approve-warning">This action is permanent and cannot be undone.</div>`}
            </div>
          `}
        </div>
      `}
    </div>
  `;
}
