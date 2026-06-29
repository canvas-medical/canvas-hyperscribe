import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;
const AI_SPARKLE = html`<span class="rec-ai-sparkle" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.3l1.72 5.72c.18.6.66 1.08 1.26 1.26L20.7 11l-5.72 1.72c-.6.18-1.08.66-1.26 1.26L12 19.7l-1.72-5.72c-.18-.6-.66-1.08-1.26-1.26L3.3 11l5.72-1.72c.6-.18 1.08-.66 1.26-1.26z"/></svg></span>`;
const ICON_SEARCH = html`<svg class="refer-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>`;

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

// canvas-core caps note_to_pharmacist at 210 chars (Surescripts NewRx wire
// limit). Exceeding that fails REVIEW with a generic ValidationError, so we
// stop the user from typing past it instead of letting them save a doomed
// command. Keep these constants aligned with
// hyperscribe/scribe/commands/_rx_validation.py.
const NOTE_TO_PHARMACIST_MAX_LENGTH = 210;
const SIG_MAX_LENGTH = 1000;
const REFILLS_MIN = 0;
const REFILLS_MAX = 99;
const RX_TAB_KEYS = new Set(['prescribe', 'refill', 'adjust_prescription']);

// Full NCPDP clinical quantity descriptions
const CLINICAL_QUANTITY_DESCRIPTIONS = [
  { code: 'C48473', label: 'Ampule' },
  { code: 'C62412', label: 'Applicator' },
  { code: 'C78783', label: 'Applicatorful' },
  { code: 'C48474', label: 'Bag' },
  { code: 'C48475', label: 'Bar' },
  { code: 'C53495', label: 'Bead' },
  { code: 'C54564', label: 'Blister' },
  { code: 'C53498', label: 'Block' },
  { code: 'C48476', label: 'Bolus' },
  { code: 'C48477', label: 'Bottle' },
  { code: 'C48478', label: 'Box' },
  { code: 'C48479', label: 'Can' },
  { code: 'C62413', label: 'Canister' },
  { code: 'C64696', label: 'Caplet' },
  { code: 'C48480', label: 'Capsule' },
  { code: 'C54702', label: 'Carton' },
  { code: 'C48481', label: 'Cartridge' },
  { code: 'C62414', label: 'Case' },
  { code: 'C69093', label: 'Cassette' },
  { code: 'C48484', label: 'Container' },
  { code: 'C48489', label: 'Cylinder' },
  { code: 'C16830', label: 'Device' },
  { code: 'C48490', label: 'Disk' },
  { code: 'C62417', label: 'Dose Pack' },
  { code: 'C96265', label: 'Dual Pack' },
  { code: 'C64933', label: 'Each' },
  { code: 'C53499', label: 'Film' },
  { code: 'C48494', label: 'Fluid Ounce' },
  { code: 'C101680', label: 'French' },
  { code: 'C48580', label: 'Gallon' },
  { code: 'C48155', label: 'Gram' },
  { code: 'C69124', label: 'Gum' },
  { code: 'C48499', label: 'Implant' },
  { code: 'C48501', label: 'Inhalation' },
  { code: 'C62275', label: 'Inhaler' },
  { code: 'C62418', label: 'Inhaler Refill' },
  { code: 'C62276', label: 'Insert' },
  { code: 'C67283', label: 'Intravenous Bag' },
  { code: 'C28252', label: 'Kilogram' },
  { code: 'C48504', label: 'Kit' },
  { code: 'C120263', label: 'Lancet' },
  { code: 'C48505', label: 'Liter' },
  { code: 'C48506', label: 'Lozenge' },
  { code: 'C48491', label: 'Metric Drop' },
  { code: 'C48512', label: 'Milliequivalent' },
  { code: 'C28253', label: 'Milligram' },
  { code: 'C28254', label: 'Milliliter' },
  { code: 'C28251', label: 'Millimeter' },
  { code: 'C71204', label: 'Nebule' },
  { code: 'C100052', label: 'Needle Free Injection' },
  { code: 'C69086', label: 'Ocular System' },
  { code: 'C48519', label: 'Ounce' },
  { code: 'C48520', label: 'Package' },
  { code: 'C48521', label: 'Packet' },
  { code: 'C65032', label: 'Pad' },
  { code: 'C82484', label: 'Paper' },
  { code: 'C48524', label: 'Patch' },
  { code: 'C120216', label: 'Pen Needle' },
  { code: 'C48529', label: 'Pint' },
  { code: 'C48530', label: 'Pouch' },
  { code: 'C48531', label: 'Pound' },
  { code: 'C97717', label: 'Pre-filled Pen Syringe' },
  { code: 'C65060', label: 'Puff' },
  { code: 'C111984', label: 'Pump' },
  { code: 'C48534', label: 'Quart' },
  { code: 'C62609', label: 'Ring' },
  { code: 'C71324', label: 'Sachet' },
  { code: 'C48536', label: 'Scoopful' },
  { code: 'C53502', label: 'Sponge' },
  { code: 'C48537', label: 'Spray' },
  { code: 'C53503', label: 'Stick' },
  { code: 'C48538', label: 'Strip' },
  { code: 'C48539', label: 'Suppository' },
  { code: 'C53504', label: 'Swab' },
  { code: 'C48540', label: 'Syringe' },
  { code: 'C48541', label: 'Tablespoon' },
  { code: 'C48542', label: 'Tablet' },
  { code: 'C62421', label: 'Tabminder' },
  { code: 'C48543', label: 'Tampon' },
  { code: 'C48544', label: 'Teaspoon' },
  { code: 'C54704', label: 'Tray' },
  { code: 'C48548', label: 'Troche' },
  { code: 'C48549', label: 'Tube' },
  { code: 'C38046', label: 'Unspecified' },
  { code: 'C48551', label: 'Vial' },
  { code: 'C48552', label: 'Wafer' },
];

/** Encode a clinical quantity option into a unique value string */
function encodeClinicalQuantity(representativeNdc, erxQuantity, qualifierCode) {
  return `${representativeNdc || ''}|${erxQuantity}|${qualifierCode}`;
}

/** Decode an encoded clinical quantity value back into its parts */
function decodeClinicalQuantity(encoded) {
  const [representative_ndc, erx_quantity, ncpdp_quantity_qualifier_code] = encoded.split('|');
  return { representative_ndc, erx_quantity: Number(erx_quantity), ncpdp_quantity_qualifier_code };
}

/** Build type-to-dispense options from a medication's quantities */
function buildTypeToDispenseOptions(quantities) {
  if (!quantities || quantities.length === 0) {
    return CLINICAL_QUANTITY_DESCRIPTIONS.map(q => ({
      value: encodeClinicalQuantity('', 1, q.code),
      label: q.label,
      representative_ndc: '',
      ncpdp_quantity_qualifier_code: q.code,
    }));
  }
  const options = [];
  for (const q of quantities) {
    options.push({
      value: encodeClinicalQuantity(q.representative_ndc, q.quantity, q.ncpdp_quantity_qualifier_code),
      label: q.clinical_quantity_description || q.ncpdp_quantity_qualifier_description,
      representative_ndc: q.representative_ndc,
      ncpdp_quantity_qualifier_code: q.ncpdp_quantity_qualifier_code,
    });
    if (
      q.clinical_quantity_description &&
      q.ncpdp_quantity_qualifier_description &&
      q.clinical_quantity_description !== q.ncpdp_quantity_qualifier_description
    ) {
      options.push({
        value: encodeClinicalQuantity(q.representative_ndc, 1, q.ncpdp_quantity_qualifier_code),
        label: q.ncpdp_quantity_qualifier_description,
        representative_ndc: q.representative_ndc,
        ncpdp_quantity_qualifier_code: q.ncpdp_quantity_qualifier_code,
      });
    }
  }
  // Deduplicate by lowercase label, keep shortest labels first.
  const seen = new Set();
  return options
    .sort((a, b) => a.label.length - b.label.length)
    .filter(o => {
      const key = o.label.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

const ORDER_TABS = [
  { key: 'prescribe', label: 'Rx' },
  { key: 'refill', label: 'Refill' },
  { key: 'adjust_prescription', label: 'Adjust' },
  { key: 'lab_order', label: 'Lab' },
  { key: 'imaging_order', label: 'Imaging' },
  { key: 'refer', label: 'Refer' },
];

const BADGE_LABELS = {
  prescribe: 'Rx',
  refill: 'Refill',
  adjust_prescription: 'Adjust',
  lab_order: 'Lab',
  imaging_order: 'Imaging',
  refer: 'Refer',
};

const REFILL_TABS = new Set(['refill', 'adjust_prescription']);

const CLINICAL_QUESTIONS = [
  'Cognitive Assistance (Advice/Guidance)',
  'Assistance with Ongoing Management',
  'Specialized intervention',
  'Diagnostic Uncertainty',
];

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return useCallback((...args) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]);
}

function buildDisplay(type, data) {
  if (type === 'prescribe') {
    const parts = [];
    if (data.medication_text) parts.push(data.medication_text);
    if (data.sig) parts.push(`Sig: ${data.sig}`);
    if (data.quantity_to_dispense) {
      const typeLabel = data.type_to_dispense_label || '';
      parts.push(`Qty: ${data.quantity_to_dispense}${typeLabel ? ` x ${typeLabel}` : ''}`);
    }
    if (data.days_supply) parts.push(`${data.days_supply}d supply`);
    if (data.refills) parts.push(`${data.refills} refill${data.refills > 1 ? 's' : ''}`);
    return parts.join(' | ') || '';
  }
  if (type === 'lab_order') {
    const parts = [];
    if (data.lab_partner_name) parts.push(data.lab_partner_name);
    if (data.test_names && data.test_names.length) parts.push(data.test_names.join(', '));
    if (data.comment) parts.push(data.comment);
    if (data.fasting_required) parts.push('Fasting');
    return parts.join(' | ') || '';
  }
  if (type === 'imaging_order') {
    const parts = [];
    if (data.image_display) parts.push(data.image_display);
    if (data.additional_details) parts.push(data.additional_details);
    if (data.comment) parts.push(data.comment);
    if (data.priority) parts.push(data.priority);
    if (data.ordering_provider_name) parts.push(data.ordering_provider_name);
    if (data.service_provider_name) parts.push(data.service_provider_name);
    return parts.join(' | ') || '';
  }
  if (type === 'refer') {
    // Headline is the specialty only; clinical_question / priority belong on the
    // detail line, not the collapsed headline.
    return data.refer_to_display || '';
  }
  return '';
}

function InteractionWarningInline({ warning }) {
  if (!warning) return null;
  const drugInteractions = warning.drug_interactions || [];
  const allergyInteractions = warning.allergy_interactions || [];
  if (drugInteractions.length === 0 && allergyInteractions.length === 0) return null;

  return html`
    <div class="interaction-warning-banner">
      <div class="interaction-warning-icon">!</div>
      <div class="interaction-warning-body">
        ${drugInteractions.length > 0 && html`
          <div class="interaction-warning-section">
            <strong>Drug-Drug Interactions</strong>
            ${drugInteractions.map((d, i) => {
              const sevText = String(d.severity_text || d.severityScreeningLevelText || d.severity || '');
              const sevLower = sevText.toLowerCase();
              const sevClass = sevLower.includes('contraindicated') ? 'severity-contraindicated'
                : sevLower.includes('severe') ? 'severity-severe'
                : sevLower.includes('moderate') ? 'severity-moderate'
                : 'severity-mild';
              const name = d.existing_medication_description || d.drugName || d.screenDrug2 || 'Unknown drug';
              const label = sevLower.includes('moderate') ? 'Moderate'
                : sevLower.includes('severe') ? 'Severe'
                : sevLower.includes('contraindicated') ? 'Contraindicated'
                : 'Warning';
              return html`<div class="interaction-warning-item" key=${i}><span class="interaction-severity-badge ${sevClass}">${label}</span> <span class="interaction-drug-name">${name}</span></div>`;
            })}
          </div>
        `}
        ${allergyInteractions.length > 0 && html`
          <div class="interaction-warning-section">
            <strong>Drug-Allergy Interactions</strong>
            ${allergyInteractions.map((a, i) => {
              const concept = a.allergy_concept || {};
              const allergen = concept.dam_allergen_concept_id_description || a.allergenName || 'Unknown allergen';
              const rawIngredients = a.allergy_ingredients || a.ingredients || [];
              const ingredients = rawIngredients.map(ing => ing.hierarchical_ingredient_code_description || ing.name || ing).filter(Boolean);
              // Show only the first unique base ingredient to avoid noise.
              const uniqueIngredients = [...new Set(ingredients)].slice(0, 3);
              return html`<div class="interaction-warning-item" key=${i}><span class="interaction-severity-badge severity-allergy">Allergy</span> <span class="interaction-drug-name">${allergen}</span>${uniqueIngredients.length > 0 && html`<span class="interaction-ingredients"> (${uniqueIngredients.join(', ')})</span>`}</div>`;
            })}
          </div>
        `}
      </div>
    </div>
  `;
}

export function OrderRow({ command, commandIndex, onEdit, onDelete, readOnly, patientId, noteId, staffId, staffName, noteDiagnoses = [], isRecommendation, onEditingChange, aiPending }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [activeTab, setActiveTab] = useState(command.command_type || 'prescribe');

  // Per-tab Rx state snapshots (saved when switching away, restored when switching back).
  const rxSnapshots = useRef({});

  const initRxState = () => ({
    medQuery: '', selectedFdb: null, selectedMedDisplay: '', medQuantities: buildTypeToDispenseOptions([]),
    sig: '', daysSupply: '', quantity: '', typeToDispense: '', refills: '',
    substitutions: true, noteToPharmacist: '', interactionWarning: null, selectedPharmacy: '', pharmacyQuery: '',
  });

  // Rx state
  const [medQuery, setMedQuery] = useState(command.data.medication_text || '');
  const [medResults, setMedResults] = useState([]);
  const [medSearching, setMedSearching] = useState(false);
  const [medSearched, setMedSearched] = useState(false);
  const [selectedFdb, setSelectedFdb] = useState(command.data.fdb_code || null);
  const [medQuantities, setMedQuantities] = useState(() => buildTypeToDispenseOptions(command.data.quantities || []));
  const [selectedMedDisplay, setSelectedMedDisplay] = useState(command.data.medication_text || '');
  const [sig, setSig] = useState(command.data.sig || '');
  const [daysSupply, setDaysSupply] = useState(command.data.days_supply != null ? String(command.data.days_supply) : '');
  const [quantity, setQuantity] = useState(command.data.quantity_to_dispense != null ? String(command.data.quantity_to_dispense) : '');
  const [typeToDispense, setTypeToDispense] = useState(command.data.type_to_dispense || '');
  const [refills, setRefills] = useState(command.data.refills != null ? String(command.data.refills) : '');
  const [substitutions, setSubstitutions] = useState(command.data.substitutions !== 'not_allowed');
  const [noteToPharmacist, setNoteToPharmacist] = useState(command.data.note_to_pharmacist || '');
  const [selectedPharmacy, setSelectedPharmacy] = useState(command.data.pharmacy || '');
  const [pharmacyQuery, setPharmacyQuery] = useState(command.data.pharmacy_name || '');
  const [pharmacyResults, setPharmacyResults] = useState([]);
  const [pharmacySearching, setPharmacySearching] = useState(false);
  const [pharmacySearched, setPharmacySearched] = useState(false);
  const [interactionWarning, setInteractionWarning] = useState(null);
  const [checkingInteractions, setCheckingInteractions] = useState(false);

  // "Change to" medication (adjust_prescription only).
  const [changeToQuery, setChangeToQuery] = useState(command.data.new_medication_text || '');
  const [changeToResults, setChangeToResults] = useState([]);
  const [changeToSearching, setChangeToSearching] = useState(false);
  const [changeToSearched, setChangeToSearched] = useState(false);
  const [changeToFdb, setChangeToFdb] = useState(command.data.new_fdb_code || null);
  const [changeToDisplay, setChangeToDisplay] = useState(command.data.new_medication_text || '');
  const changeToTimer = useRef(null);

  const handleChangeToInput = (e) => {
    const val = e.target.value;
    setChangeToQuery(val);
    setChangeToFdb(null);
    setChangeToDisplay('');
    if (changeToTimer.current) clearTimeout(changeToTimer.current);
    if (val.length < 2) { setChangeToResults([]); setChangeToSearched(false); return; }
    changeToTimer.current = setTimeout(async () => {
      setChangeToSearching(true);
      try {
        const res = await fetch(`${API_BASE}/search-medications?query=${encodeURIComponent(val)}`);
        const data = await res.json();
        setChangeToResults(data.results || []);
      } catch (err) { setChangeToResults([]); }
      finally { setChangeToSearching(false); setChangeToSearched(true); }
    }, 300);
  };

  const handleChangeToSelect = (r) => {
    setChangeToFdb(r.fdb_code);
    setChangeToDisplay(r.description);
    setChangeToQuery(r.description);
    setChangeToResults([]);
    setChangeToSearched(false);
  };

  const snapshotCurrentRx = () => ({
    medQuery, selectedFdb, selectedMedDisplay, medQuantities,
    sig, daysSupply, quantity, typeToDispense, refills,
    substitutions, noteToPharmacist, interactionWarning, selectedPharmacy, pharmacyQuery,
  });

  const restoreRxSnapshot = (snap) => {
    setMedQuery(snap.medQuery);
    setSelectedFdb(snap.selectedFdb);
    setSelectedMedDisplay(snap.selectedMedDisplay);
    setMedQuantities(snap.medQuantities);
    setSig(snap.sig);
    setDaysSupply(snap.daysSupply);
    setQuantity(snap.quantity);
    setTypeToDispense(snap.typeToDispense);
    setRefills(snap.refills);
    setSubstitutions(snap.substitutions);
    setNoteToPharmacist(snap.noteToPharmacist);
    setSelectedPharmacy(snap.selectedPharmacy);
    setPharmacyQuery(snap.pharmacyQuery);
    setInteractionWarning(snap.interactionWarning);
    setMedResults([]);
    setMedSearched(false);
  };

  // Refill state
  const [refillMeds, setRefillMeds] = useState([]);
  const [refillLoading, setRefillLoading] = useState(false);

  useEffect(() => {
    if (!REFILL_TABS.has(activeTab) || !patientId) return;
    let cancelled = false;
    setRefillLoading(true);
    fetch(`${API_BASE}/patient-medications-for-refill?patient_id=${encodeURIComponent(patientId)}`)
      .then(r => r.json())
      .then(json => { if (!cancelled) setRefillMeds(json.medications || []); })
      .catch(() => setRefillMeds([]))
      .finally(() => { if (!cancelled) setRefillLoading(false); });
    return () => { cancelled = true; };
  }, [activeTab, patientId]);

  // Load patient's preferred pharmacies when the Rx tab is first active.
  const preferredPharmaciesLoaded = useRef(false);
  useEffect(() => {
    if (activeTab !== 'prescribe' && !REFILL_TABS.has(activeTab)) return;
    if (!patientId || preferredPharmaciesLoaded.current || selectedPharmacy) return;
    preferredPharmaciesLoaded.current = true;
    fetch(`${API_BASE}/search-pharmacies?patient_id=${encodeURIComponent(patientId)}`)
      .then(r => r.json())
      .then(d => {
        const list = d.results || [];
        setPharmacyResults(list);
        const defaultPharm = list.find(p => p.preferred);
        if (defaultPharm) {
          setSelectedPharmacy(defaultPharm.ncpdp_id);
          setPharmacyQuery(defaultPharm.name);
        }
      })
      .catch(() => {});
  }, [activeTab, patientId]);

  const doPharmacySearch = useCallback(async (q) => {
    if (!q || q.length < 2) {
      setPharmacyResults([]);
      setPharmacySearched(false);
      return;
    }
    setPharmacySearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-pharmacies?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      setPharmacyResults(data.results || []);
    } catch (err) {
      setPharmacyResults([]);
    } finally {
      setPharmacySearching(false);
      setPharmacySearched(true);
    }
  }, []);

  const debouncedPharmacySearch = useDebounce(doPharmacySearch, DEBOUNCE_MS);

  const handlePharmacyInput = (e) => {
    const val = e.target.value;
    setPharmacyQuery(val);
    setSelectedPharmacy('');
    debouncedPharmacySearch(val);
  };

  const handlePharmacySelect = (pharmacy) => {
    setSelectedPharmacy(pharmacy.ncpdp_id);
    const display = [pharmacy.name, pharmacy.address].filter(Boolean).join(' — ');
    setPharmacyQuery(display || pharmacy.ncpdp_id);
    setPharmacyResults([]);
    setPharmacySearched(false);
  };

  const handleRefillSelect = async (e) => {
    const idx = parseInt(e.target.value, 10);
    if (isNaN(idx)) return;
    const item = refillMeds[idx];
    if (!item) return;
    // Pre-fill all Rx state from the selected medication's last prescription.
    setSelectedFdb(item.fdb_code);
    setSelectedMedDisplay(item.medication_name);
    setMedQuery(item.medication_name);
    setSig(item.sig || '');
    setDaysSupply(item.days_supply != null ? String(item.days_supply) : '');
    setQuantity(item.quantity_to_dispense != null ? String(item.quantity_to_dispense) : '');
    setRefills(item.refills != null ? String(item.refills) : '');
    setSubstitutions(item.substitutions !== 'not_allowed');
    setNoteToPharmacist(item.note_to_pharmacist || '');
    // Fetch proper quantity options from the medication search endpoint.
    const qualifierCode = item.potency_unit_code || '';
    try {
      const res = await fetch(`${API_BASE}/search-medications?query=${encodeURIComponent(item.medication_name)}`);
      const data = await res.json();
      const match = (data.results || []).find(r => r.fdb_code === item.fdb_code);
      if (match && match.quantities && match.quantities.length > 0) {
        const options = buildTypeToDispenseOptions(match.quantities);
        setMedQuantities(options);
        // Auto-select the option matching the medication's potency unit code.
        const selected = qualifierCode
          ? options.find(o => decodeClinicalQuantity(o.value).ncpdp_quantity_qualifier_code === qualifierCode)
          : options.length === 1 ? options[0] : null;
        setTypeToDispense(selected ? selected.value : '');
      } else {
        setMedQuantities(buildTypeToDispenseOptions([]));
        setTypeToDispense('');
      }
    } catch (err) {
      // Fallback: use generic options with the potency unit code.
      const options = buildTypeToDispenseOptions([]);
      setMedQuantities(options);
      if (qualifierCode) {
        const ndc = item.national_drug_code || '';
        const encoded = encodeClinicalQuantity(ndc, 1, qualifierCode);
        const fallback = options.find(o => decodeClinicalQuantity(o.value).ncpdp_quantity_qualifier_code === qualifierCode);
        setTypeToDispense(fallback ? fallback.value : encoded);
      } else {
        setTypeToDispense('');
      }
    }
  };

  const checkInteractions = useCallback(async (fdbCode, medName) => {
    if (!noteId || (!fdbCode && !medName)) {
      setInteractionWarning(null);
      return;
    }
    setCheckingInteractions(true);
    try {
      const params = new URLSearchParams({ note_id: noteId });
      if (fdbCode) params.set('fdb_code', fdbCode);
      if (medName) params.set('medication_name', medName);
      const res = await fetch(`${API_BASE}/check-interactions?${params}`);
      const data = await res.json();
      const hasDrug = (data.drug_interactions || []).length > 0;
      const hasAllergy = (data.allergy_interactions || []).length > 0;
      setInteractionWarning((hasDrug || hasAllergy) ? data : null);
    } catch (err) {
      console.error('Interaction check failed:', err);
      setInteractionWarning(null);
    } finally {
      setCheckingInteractions(false);
    }
  }, [noteId]);

  // Check interactions on mount if we already have a medication selected.
  useEffect(() => {
    if (command.command_type === 'prescribe' && (command.data.fdb_code || command.data.medication_text)) {
      checkInteractions(command.data.fdb_code, command.data.medication_text);
    }
  }, []);

  // Lab state
  const [labPartners, setLabPartners] = useState([]);
  const [labPartnerId, setLabPartnerId] = useState(command.data.lab_partner || '');
  const [labPartnerName, setLabPartnerName] = useState(command.data.lab_partner_name || '');
  const [labTestQuery, setLabTestQuery] = useState('');
  const [labTestResults, setLabTestResults] = useState([]);
  const [labTestSearching, setLabTestSearching] = useState(false);
  const [labTestSearched, setLabTestSearched] = useState(false);
  const [selectedTests, setSelectedTests] = useState(
    (command.data.tests_order_codes || []).map((code, i) => ({
      order_code: code,
      order_name: (command.data.test_names || [])[i] || code,
    }))
  );
  const [selectedDiagnoses, setSelectedDiagnoses] = useState(
    (command.data.diagnosis_codes || []).map((code, i) => ({
      code,
      display: (command.data.diagnosis_displays || [])[i] || code,
    }))
  );
  const [diagQuery, setDiagQuery] = useState('');
  const [diagResults, setDiagResults] = useState([]);
  const [diagSearching, setDiagSearching] = useState(false);
  const [diagSearched, setDiagSearched] = useState(false);
  const [diagFocused, setDiagFocused] = useState(false);
  const [patientConditions, setPatientConditions] = useState([]);
  const [labFasting, setLabFasting] = useState(command.data.fasting_required || false);
  const [labComment, setLabComment] = useState(command.data.comment || '');
  const labTestInputRef = useRef(null);
  const diagInputRef = useRef(null);

  // Imaging state
  const [imagingQuery, setImagingQuery] = useState(command.data.image_display || '');
  const [imagingResults, setImagingResults] = useState([]);
  const [imagingSearching, setImagingSearching] = useState(false);
  const [imagingSearched, setImagingSearched] = useState(false);
  const [selectedImageCode, setSelectedImageCode] = useState(command.data.image_code || null);
  const [selectedImageDisplay, setSelectedImageDisplay] = useState(command.data.image_display || '');
  const [imagingDiagnoses, setImagingDiagnoses] = useState(
    (command.data.diagnosis_codes || []).map((code, i) => ({
      code,
      display: (command.data.diagnosis_displays || [])[i] || code,
      formatted_code: (command.data.diagnosis_formatted || [])[i] || code,
    }))
  );
  const [imagingDiagQuery, setImagingDiagQuery] = useState('');
  const [imagingDiagResults, setImagingDiagResults] = useState([]);
  const [imagingDiagSearching, setImagingDiagSearching] = useState(false);
  const [imagingDiagSearched, setImagingDiagSearched] = useState(false);
  const [imagingDiagFocused, setImagingDiagFocused] = useState(false);
  const [imagingDetails, setImagingDetails] = useState(command.data.additional_details || '');
  const [imagingComment, setImagingComment] = useState(command.data.comment || '');
  const [imagingPriority, setImagingPriority] = useState(command.data.priority || 'Routine');
  const [orderingProviders, setOrderingProviders] = useState([]);
  const [orderingProviderId, setOrderingProviderId] = useState(command.data.ordering_provider_id || '');
  const [orderingProviderName, setOrderingProviderName] = useState(command.data.ordering_provider_name || '');
  const [providerQuery, setProviderQuery] = useState('');
  const [providerDropdownOpen, setProviderDropdownOpen] = useState(false);
  const [centerQuery, setCenterQuery] = useState('');
  const [centerResults, setCenterResults] = useState([]);
  const [centerSearching, setCenterSearching] = useState(false);
  const [centerSearched, setCenterSearched] = useState(false);
  const [selectedCenter, setSelectedCenter] = useState(command.data.service_provider || null);
  const [selectedCenterName, setSelectedCenterName] = useState(command.data.service_provider_name || '');
  const imagingInputRef = useRef(null);
  const imagingDiagInputRef = useRef(null);
  const centerInputRef = useRef(null);

  // Refer state
  const [referProvider, setReferProvider] = useState(command.data.service_provider || null);
  const [referProviderDisplay, setReferProviderDisplay] = useState(command.data.refer_to_display || '');
  const [referProviderQuery, setReferProviderQuery] = useState('');
  const [referProviderResults, setReferProviderResults] = useState([]);
  const [referProviderSearching, setReferProviderSearching] = useState(false);
  const [referProviderSearched, setReferProviderSearched] = useState(false);
  const [referDiagnoses, setReferDiagnoses] = useState(
    (command.data.diagnosis_codes || []).map((code, i) => ({
      code,
      display: (command.data.diagnosis_displays || [])[i] || code,
      formatted_code: (command.data.diagnosis_formatted || [])[i] || code,
    }))
  );
  const [referDiagQuery, setReferDiagQuery] = useState('');
  const [referDiagResults, setReferDiagResults] = useState([]);
  const [referDiagSearching, setReferDiagSearching] = useState(false);
  const [referDiagSearched, setReferDiagSearched] = useState(false);
  const [referDiagFocused, setReferDiagFocused] = useState(false);
  const [referClinicalQuestion, setReferClinicalQuestion] = useState(command.data.clinical_question || '');
  const [referPriority, setReferPriority] = useState(command.data.priority || '');
  const [referNotesToSpecialist, setReferNotesToSpecialist] = useState(command.data.notes_to_specialist || '');
  const [referComment, setReferComment] = useState(command.data.comment || '');
  const [referCommentOpen, setReferCommentOpen] = useState(!!(command.data.comment));
  const [referPriorityOpen, setReferPriorityOpen] = useState(!!(command.data.priority));
  const referProviderInputRef = useRef(null);
  const referDiagInputRef = useRef(null);

  const medInputRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (editing && activeTab === 'prescribe' && medInputRef.current) {
      medInputRef.current.focus({ preventScroll: true });
    }
  }, [editing, activeTab]);

  // Load lab partners when lab tab is active.
  useEffect(() => {
    if (activeTab !== 'lab_order' || labPartners.length > 0) return;
    fetch(`${API_BASE}/lab-partners`)
      .then(r => r.json())
      .then(d => setLabPartners(d.lab_partners || []))
      .catch(() => {});
  }, [activeTab]);

  // Load ordering providers when imaging tab is active.
  useEffect(() => {
    if (activeTab !== 'imaging_order' || orderingProviders.length > 0) return;
    fetch(`${API_BASE}/ordering-providers`)
      .then(r => r.json())
      .then(d => {
        const providers = d.providers || [];
        setOrderingProviders(providers);
        if (!orderingProviderId && staffId && providers.some(p => p.id === staffId)) {
          setOrderingProviderId(staffId);
          setOrderingProviderName(staffName || '');
        }
      })
      .catch(() => {});
  }, [activeTab]);

  // Load patient conditions when lab, imaging, or refer tab is active.
  useEffect(() => {
    if (activeTab !== 'lab_order' && activeTab !== 'imaging_order' && activeTab !== 'refer') return;
    if (!patientId || patientConditions.length > 0) return;
    fetch(`${API_BASE}/patient-conditions?patient_id=${encodeURIComponent(patientId)}`)
      .then(r => r.json())
      .then(d => setPatientConditions(d.conditions || []))
      .catch(() => {});
  }, [activeTab]);

  const doLabTestSearch = useCallback(async (q) => {
    if (!labPartnerId || !q || q.length < 2) { setLabTestResults([]); setLabTestSearched(false); return; }
    setLabTestSearching(true);
    try {
      const res = await fetch(
        `${API_BASE}/lab-partner-tests?partner_id=${encodeURIComponent(labPartnerId)}&query=${encodeURIComponent(q)}`
      );
      const data = await res.json();
      const alreadySelected = new Set(selectedTests.map(t => t.order_code));
      setLabTestResults((data.tests || []).filter(t => !alreadySelected.has(t.order_code)));
    } catch (err) {
      setLabTestResults([]);
    } finally {
      setLabTestSearching(false);
      setLabTestSearched(true);
    }
  }, [labPartnerId, selectedTests]);

  const debouncedLabTestSearch = useDebounce(doLabTestSearch, DEBOUNCE_MS);

  const handleLabTestInput = (e) => {
    const val = e.target.value;
    setLabTestQuery(val);
    debouncedLabTestSearch(val);
  };

  const handleLabTestSelect = (test) => {
    setSelectedTests([...selectedTests, test]);
    setLabTestQuery('');
    setLabTestResults([]);
    if (labTestInputRef.current) labTestInputRef.current.focus({ preventScroll: true });
  };

  const handleLabTestRemove = (orderCode) => {
    setSelectedTests(selectedTests.filter(t => t.order_code !== orderCode));
  };

  const handleLabPartnerChange = (e) => {
    const id = e.target.value;
    setLabPartnerId(id);
    const partner = labPartners.find(p => p.id === id);
    setLabPartnerName(partner ? partner.name : '');
    setSelectedTests([]);
    setLabTestQuery('');
    setLabTestResults([]);
    setLabTestSearched(false);
  };

  const doDiagSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setDiagResults([]); setDiagSearched(false); return; }
    setDiagSearching(true);
    try {
      const res = await fetch(
        `${API_BASE}/search-diagnoses?query=${encodeURIComponent(q)}`
      );
      const data = await res.json();
      const alreadySelected = new Set(selectedDiagnoses.map(d => d.code));
      setDiagResults((data.results || []).filter(d => !alreadySelected.has(d.code)));
    } catch (err) {
      setDiagResults([]);
    } finally {
      setDiagSearching(false);
      setDiagSearched(true);
    }
  }, [selectedDiagnoses]);

  const debouncedDiagSearch = useDebounce(doDiagSearch, DEBOUNCE_MS);

  const handleDiagInput = (e) => {
    const val = e.target.value;
    setDiagQuery(val);
    debouncedDiagSearch(val);
  };

  const handleDiagSelect = (diag) => {
    setSelectedDiagnoses([...selectedDiagnoses, diag]);
    setDiagQuery('');
    setDiagResults([]);
    setDiagSearched(false);
    if (diagInputRef.current) diagInputRef.current.focus({ preventScroll: true });
  };

  const handleDiagRemove = (code) => {
    setSelectedDiagnoses(selectedDiagnoses.filter(d => d.code !== code));
  };

  const diagSuggestions = (() => {
    if (!diagQuery && patientConditions.length > 0) {
      const alreadySelected = new Set(selectedDiagnoses.map(d => d.code));
      return patientConditions.filter(c => !alreadySelected.has(c.code));
    }
    return [];
  })();

  // Imaging code search.
  const doImagingSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setImagingResults([]); setImagingSearched(false); return; }
    setImagingSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-imaging?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      setImagingResults(data.results || []);
    } catch (err) {
      setImagingResults([]);
    } finally {
      setImagingSearching(false);
      setImagingSearched(true);
    }
  }, []);

  const debouncedImagingSearch = useDebounce(doImagingSearch, DEBOUNCE_MS);

  const handleImagingInput = (e) => {
    const val = e.target.value;
    setImagingQuery(val);
    setSelectedImageCode(null);
    setSelectedImageDisplay(val);
    debouncedImagingSearch(val);
  };

  const handleImagingSelect = (result) => {
    setSelectedImageCode(result.value);
    setSelectedImageDisplay(result.display);
    setImagingQuery(result.display);
    setImagingResults([]);
    setImagingSearched(false);
  };

  // Imaging diagnosis search.
  const doImagingDiagSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setImagingDiagResults([]); setImagingDiagSearched(false); return; }
    setImagingDiagSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-diagnoses?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      const alreadySelected = new Set(imagingDiagnoses.map(d => d.code));
      setImagingDiagResults((data.results || []).filter(d => !alreadySelected.has(d.code)));
    } catch (err) {
      setImagingDiagResults([]);
    } finally {
      setImagingDiagSearching(false);
      setImagingDiagSearched(true);
    }
  }, [imagingDiagnoses]);

  const debouncedImagingDiagSearch = useDebounce(doImagingDiagSearch, DEBOUNCE_MS);

  const handleImagingDiagInput = (e) => {
    const val = e.target.value;
    setImagingDiagQuery(val);
    debouncedImagingDiagSearch(val);
  };

  const handleImagingDiagSelect = (diag) => {
    setImagingDiagnoses([...imagingDiagnoses, diag]);
    setImagingDiagQuery('');
    setImagingDiagResults([]);
    setImagingDiagSearched(false);
    if (imagingDiagInputRef.current) imagingDiagInputRef.current.focus({ preventScroll: true });
  };

  const handleImagingDiagRemove = (code) => {
    setImagingDiagnoses(imagingDiagnoses.filter(d => d.code !== code));
  };

  const imagingDiagSuggestions = (() => {
    if (!imagingDiagQuery && patientConditions.length > 0) {
      const alreadySelected = new Set(imagingDiagnoses.map(d => d.code));
      return patientConditions.filter(c => !alreadySelected.has(c.code));
    }
    return [];
  })();

  const handleProviderInput = (e) => {
    setProviderQuery(e.target.value);
    setProviderDropdownOpen(true);
    if (!e.target.value) {
      setOrderingProviderId('');
      setOrderingProviderName('');
    }
  };

  const handleProviderSelect = (provider) => {
    setOrderingProviderId(provider.id);
    setOrderingProviderName(provider.label);
    setProviderQuery('');
    setProviderDropdownOpen(false);
  };

  const filteredProviders = providerQuery
    ? orderingProviders.filter(p => p.label.toLowerCase().includes(providerQuery.toLowerCase()))
    : orderingProviders;

  // Imaging center search.
  const doCenterSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setCenterResults([]); setCenterSearched(false); return; }
    setCenterSearching(true);
    try {
      let url = `${API_BASE}/search-imaging-centers?query=${encodeURIComponent(q)}`;
      if (patientId) url += `&patient_id=${encodeURIComponent(patientId)}`;
      if (noteId) url += `&note_id=${encodeURIComponent(noteId)}`;
      const res = await fetch(url);
      const data = await res.json();
      setCenterResults(data.results || []);
    } catch (err) {
      setCenterResults([]);
    } finally {
      setCenterSearching(false);
      setCenterSearched(true);
    }
  }, [patientId, noteId]);

  const debouncedCenterSearch = useDebounce(doCenterSearch, DEBOUNCE_MS);

  const handleCenterInput = (e) => {
    const val = e.target.value;
    setCenterQuery(val);
    setSelectedCenter(null);
    setSelectedCenterName(val);
    debouncedCenterSearch(val);
  };

  const handleCenterSelect = (result) => {
    setSelectedCenter(result.data);
    setSelectedCenterName(result.name);
    setCenterQuery('');
    setCenterResults([]);
    setCenterSearched(false);
  };

  // Refer-to provider search.
  const doReferProviderSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setReferProviderResults([]); setReferProviderSearched(false); return; }
    setReferProviderSearching(true);
    try {
      let url = `${API_BASE}/search-refer-providers?query=${encodeURIComponent(q)}`;
      if (patientId) url += `&patient_id=${encodeURIComponent(patientId)}`;
      if (noteId) url += `&note_id=${encodeURIComponent(noteId)}`;
      const res = await fetch(url);
      const data = await res.json();
      setReferProviderResults(data.results || []);
    } catch (err) {
      setReferProviderResults([]);
    } finally {
      setReferProviderSearching(false);
      setReferProviderSearched(true);
    }
  }, [patientId, noteId]);

  const debouncedReferProviderSearch = useDebounce(doReferProviderSearch, DEBOUNCE_MS);

  const handleReferProviderInput = (e) => {
    const val = e.target.value;
    setReferProviderQuery(val);
    debouncedReferProviderSearch(val);
  };

  const handleReferProviderSelect = (result) => {
    setReferProvider(result.data);
    setReferProviderDisplay(result.name);
    setReferProviderQuery('');
    setReferProviderResults([]);
    setReferProviderSearched(false);
  };

  // Refer diagnosis search.
  const doReferDiagSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setReferDiagResults([]); setReferDiagSearched(false); return; }
    setReferDiagSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-diagnoses?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      const alreadySelected = new Set(referDiagnoses.map(d => d.code));
      setReferDiagResults((data.results || []).filter(d => !alreadySelected.has(d.code)));
    } catch (err) {
      setReferDiagResults([]);
    } finally {
      setReferDiagSearching(false);
      setReferDiagSearched(true);
    }
  }, [referDiagnoses]);

  const debouncedReferDiagSearch = useDebounce(doReferDiagSearch, DEBOUNCE_MS);

  const handleReferDiagInput = (e) => {
    const val = e.target.value;
    setReferDiagQuery(val);
    debouncedReferDiagSearch(val);
  };

  const handleReferDiagSelect = (diag) => {
    // cap indications at 2 so the field stays a single fixed-size line
    if (referDiagnoses.length >= 2 || referDiagnoses.some(d => d.code === diag.code)) return;
    setReferDiagnoses([...referDiagnoses, diag]);
    setReferDiagQuery('');
    setReferDiagResults([]);
    setReferDiagSearched(false);
    // Close the dropdown after a selection; the provider can click back into
    // the field to search for another indication.
    setReferDiagFocused(false);
    if (referDiagInputRef.current) referDiagInputRef.current.blur();
  };

  const handleReferDiagRemove = (code) => {
    setReferDiagnoses(referDiagnoses.filter(d => d.code !== code));
  };

  // Tolerant ICD-10 code key so the same diagnosis from different sources
  // (chart conditions, live search, staged note dx) dedups regardless of dot
  // formatting or case.
  const normDiagCode = (c) => (c || '').replace(/[^a-z0-9]/gi, '').toUpperCase();

  // Diagnoses staged in this note's A&P, shown first as the most relevant
  // indications. Excludes anything already selected as a chip.
  const noteDiagSuggestions = (() => {
    if (referDiagQuery || !noteDiagnoses || noteDiagnoses.length === 0) return [];
    const selected = new Set(referDiagnoses.map(d => normDiagCode(d.code)));
    const seen = new Set();
    return noteDiagnoses.filter(d => {
      const key = normDiagCode(d.code);
      if (!key || selected.has(key) || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  })();

  const referDiagSuggestions = (() => {
    if (!referDiagQuery && patientConditions.length > 0) {
      const alreadySelected = new Set(referDiagnoses.map(d => normDiagCode(d.code)));
      // Suppress chart conditions already surfaced under "From this note".
      const noteCodes = new Set(noteDiagSuggestions.map(d => normDiagCode(d.code)));
      return patientConditions.filter(c =>
        !alreadySelected.has(normDiagCode(c.code)) && !noteCodes.has(normDiagCode(c.code)));
    }
    return [];
  })();

  // Close dropdown on outside click.
  useEffect(() => {
    if (!editing) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setMedResults([]);
        setMedSearched(false);
        setLabTestResults([]);
        setLabTestSearched(false);
        setDiagResults([]);
        setDiagSearched(false);
        setDiagFocused(false);
        setImagingResults([]);
        setImagingSearched(false);
        setImagingDiagResults([]);
        setImagingDiagSearched(false);
        setImagingDiagFocused(false);
        setProviderResults([]);
        setCenterResults([]);
        setCenterSearched(false);
        setReferProviderResults([]);
        setReferProviderSearched(false);
        setReferDiagResults([]);
        setReferDiagSearched(false);
        setReferDiagFocused(false);
        setPharmacyResults([]);
        setPharmacySearched(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [editing]);

  const doMedSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setMedResults([]); setMedSearched(false); return; }
    setMedSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-medications?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      setMedResults(data.results || []);
    } catch (err) {
      setMedResults([]);
    } finally {
      setMedSearching(false);
      setMedSearched(true);
    }
  }, []);

  const debouncedMedSearch = useDebounce(doMedSearch, DEBOUNCE_MS);

  const handleMedInput = (e) => {
    const val = e.target.value;
    setMedQuery(val);
    setSelectedFdb(null);
    setMedQuantities(buildTypeToDispenseOptions([]));
    setSelectedMedDisplay(val);
    debouncedMedSearch(val);
  };

  const handleMedSelect = (result) => {
    setSelectedFdb(result.fdb_code);
    setSelectedMedDisplay(result.description);
    setMedQuery(result.description);
    setMedResults([]);
    setMedSearched(false);
    const options = buildTypeToDispenseOptions(result.quantities || []);
    setMedQuantities(options);
    if (options.length === 1) {
      setTypeToDispense(options[0].value);
    } else {
      setTypeToDispense('');
    }
    checkInteractions(result.fdb_code, result.description);
  };

  const handleSave = () => {
    let data = {};
    if (activeTab === 'prescribe' || REFILL_TABS.has(activeTab)) {
      if (!selectedMedDisplay.trim()) return;
      const selectedQty = medQuantities.find(q => q.value === typeToDispense);
      const decoded = typeToDispense ? decodeClinicalQuantity(typeToDispense) : null;
      data = {
        fdb_code: selectedFdb || null,
        medication_text: selectedMedDisplay,
        sig,
        days_supply: daysSupply !== '' ? Number(daysSupply) : null,
        quantity_to_dispense: quantity !== '' ? Number(quantity) : null,
        type_to_dispense: decoded ? decoded.ncpdp_quantity_qualifier_code : null,
        type_to_dispense_label: selectedQty ? selectedQty.label : null,
        representative_ndc: decoded ? decoded.representative_ndc : null,
        refills: refills !== '' ? Number(refills) : null,
        substitutions: substitutions ? 'allowed' : 'not_allowed',
        note_to_pharmacist: noteToPharmacist || null,
        pharmacy: selectedPharmacy || null,
        pharmacy_name: selectedPharmacy ? pharmacyQuery : null,
        quantities: medQuantities.map(q => ({ representative_ndc: q.representative_ndc, ncpdp_quantity_qualifier_code: q.ncpdp_quantity_qualifier_code, clinical_quantity_description: q.label, quantity: 1 })),
      };
      // Include "change to" medication for adjust_prescription.
      if (activeTab === 'adjust_prescription' && changeToFdb) {
        data.new_fdb_code = changeToFdb;
        data.new_medication_text = changeToDisplay;
      }
    } else if (activeTab === 'lab_order') {
      data = {
        lab_partner: labPartnerId || null,
        lab_partner_name: labPartnerName || null,
        tests_order_codes: selectedTests.map(t => t.order_code),
        test_names: selectedTests.map(t => t.order_name),
        diagnosis_codes: selectedDiagnoses.map(d => d.code),
        diagnosis_displays: selectedDiagnoses.map(d => d.display),
        fasting_required: labFasting,
        comment: labComment || null,
      };
    } else if (activeTab === 'imaging_order') {
      data = {
        image_code: selectedImageCode || null,
        image_display: selectedImageDisplay || null,
        diagnosis_codes: imagingDiagnoses.map(d => d.code),
        diagnosis_displays: imagingDiagnoses.map(d => d.display),
        diagnosis_formatted: imagingDiagnoses.map(d => d.formatted_code || d.code),
        additional_details: imagingDetails || null,
        comment: imagingComment || null,
        priority: imagingPriority,
        ordering_provider_id: orderingProviderId || null,
        ordering_provider_name: orderingProviderName || null,
        service_provider: selectedCenter || null,
        service_provider_name: selectedCenterName || null,
      };
    } else if (activeTab === 'refer') {
      data = {
        service_provider: referProvider || null,
        refer_to_display: referProviderDisplay || null,
        diagnosis_codes: referDiagnoses.map(d => d.code),
        diagnosis_displays: referDiagnoses.map(d => d.display),
        diagnosis_formatted: referDiagnoses.map(d => d.formatted_code || d.code),
        clinical_question: referClinicalQuestion || null,
        priority: referPriority || null,
        notes_to_specialist: referNotesToSpecialist || null,
        comment: referComment || null,
      };
    }
    onEdit(commandIndex, data, activeTab);
    setEditing(false);
  };

  const handleCancel = () => {
    if (isNew) {
      onDelete(commandIndex);
      return;
    }
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  if (editing && !readOnly) {
    return html`
      <div class="order-row editing" ref=${containerRef} onKeyDown=${handleKeyDown}>
        <div class="history-form">
          ${!isRecommendation && html`
            <div class="order-tabs-horizontal">
              ${ORDER_TABS.map(tab => html`
                <button
                  key=${tab.key}
                  type="button"
                  class="order-tab-h${activeTab === tab.key ? ' active' : ''}"
                  onClick=${() => {
                    if (tab.key === activeTab) return;
                    // Save current Rx state for this tab.
                    const RX_TABS = new Set(['prescribe', 'refill', 'adjust_prescription']);
                    if (RX_TABS.has(activeTab)) {
                      rxSnapshots.current[activeTab] = snapshotCurrentRx();
                    }
                    // Restore or reset Rx state for the target tab.
                    if (RX_TABS.has(tab.key) && rxSnapshots.current[tab.key]) {
                      restoreRxSnapshot(rxSnapshots.current[tab.key]);
                    } else if (RX_TABS.has(tab.key)) {
                      restoreRxSnapshot(initRxState());
                    }
                    setActiveTab(tab.key);
                  }}
                >${tab.label}</button>
              `)}
            </div>
          `}
          <div class="order-form">
            ${(activeTab === 'prescribe' || (REFILL_TABS.has(activeTab) && selectedFdb)) && (() => {
              // The required-field set here matches
              // hyperscribe/scribe/commands/_rx_validation.py and the
              // canvas-core Prescribe schema. Refills must also be 0-99 and
              // an integer; quantity must be > 0 and not have trailing zeros.
              const rxMissing = new Set();
              if (!selectedFdb) rxMissing.add('medication');
              const qtyNum = quantity === '' || quantity == null ? null : Number(quantity);
              const qtyStr = String(quantity ?? '').trim();
              if (qtyNum == null || Number.isNaN(qtyNum) || qtyNum <= 0
                  || (qtyStr.includes('.') && (qtyStr.endsWith('0') || qtyStr.endsWith('.')))) {
                rxMissing.add('qty');
              }
              if (!typeToDispense) rxMissing.add('type');
              if (!sig || sig.length > SIG_MAX_LENGTH) rxMissing.add('sig');
              const refillsNum = refills === '' || refills == null ? null : Number(refills);
              if (refillsNum == null || Number.isNaN(refillsNum) || !Number.isInteger(refillsNum)
                  || refillsNum < REFILLS_MIN || refillsNum > REFILLS_MAX) {
                rxMissing.add('refills');
              }
              return html`
              <div class="order-form">
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label${rxMissing.has('medication') ? ' field-missing' : ''}">Medication *</label>
                  <input
                    ref=${medInputRef}
                    type="text"
                    class="history-form-input${rxMissing.has('medication') ? ' input-missing' : ''}"
                    value=${medQuery}
                    onInput=${handleMedInput}
                    placeholder="Search medications..."
                  />
                  ${medSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${medResults.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${medResults.map(r => html`
                        <div
                          key=${r.fdb_code}
                          class="history-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleMedSelect(r); }}
                        >${r.description}</div>
                      `)}
                    </div>
                  `}
                  ${!medSearching && medSearched && medResults.length === 0 && medQuery.length >= 2 && html`
                    <div class="history-search-dropdown">
                      <div class="history-search-result search-no-results">No medications found</div>
                    </div>
                  `}
                </div>
                ${activeTab === 'adjust_prescription' && html`
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Change to (optional)</label>
                  <input
                    type="text"
                    class="history-form-input"
                    value=${changeToQuery}
                    onInput=${handleChangeToInput}
                    placeholder="Search new medication..."
                  />
                  ${changeToSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${changeToResults.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${changeToResults.map(r => html`
                        <div key=${r.fdb_code} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleChangeToSelect(r); }}>${r.description}</div>
                      `)}
                    </div>
                  `}
                  ${!changeToSearching && changeToSearched && changeToResults.length === 0 && changeToQuery.length >= 2 && html`
                    <div class="history-search-dropdown"><div class="history-search-result search-no-results">No medications found</div></div>
                  `}
                </div>
                `}
                <div class="order-rx-grid">
                  <div class="history-form-field">
                    <label class="history-form-label${rxMissing.has('qty') ? ' field-missing' : ''}">Qty *</label>
                    <input class="history-form-input${rxMissing.has('qty') ? ' input-missing' : ''}" type="number" value=${quantity} onInput=${(e) => setQuantity(e.target.value)} min="0" placeholder="—" />
                  </div>
                  <div class="history-form-field">
                    <label class="history-form-label${rxMissing.has('type') ? ' field-missing' : ''}">Dispense type *</label>
                    <select class="history-form-input${rxMissing.has('type') ? ' input-missing' : ''}" value=${typeToDispense} onChange=${(e) => setTypeToDispense(e.target.value)}>
                      <option value="">Select...</option>
                      ${medQuantities.map(o => html`
                        <option key=${o.value} value=${o.value}>${o.label}</option>
                      `)}
                    </select>
                  </div>
                  <div class="history-form-field">
                    <label class="history-form-label">Days supply</label>
                    <input class="history-form-input" type="number" value=${daysSupply} onInput=${(e) => setDaysSupply(e.target.value)} min="0" step="1" placeholder="—" />
                  </div>
                  <div class="history-form-field">
                    <label class="history-form-label${rxMissing.has('refills') ? ' field-missing' : ''}">Refills *</label>
                    <input class="history-form-input${rxMissing.has('refills') ? ' input-missing' : ''}" type="number" value=${refills} onInput=${(e) => setRefills(e.target.value)} min="0" placeholder="—" />
                  </div>
                </div>
                <div class="history-form-field">
                  <label class="history-form-label${rxMissing.has('sig') ? ' field-missing' : ''}">Sig *</label>
                  <input class="history-form-input${rxMissing.has('sig') ? ' input-missing' : ''}" type="text" maxLength=${SIG_MAX_LENGTH} value=${sig} onInput=${(e) => setSig(e.target.value)} placeholder="e.g. Take 1 tablet by mouth daily" />
                  <div class="char-counter${sig.length > SIG_MAX_LENGTH - 100 ? sig.length > SIG_MAX_LENGTH ? ' over-limit' : ' near-limit' : ''}">${sig.length} / ${SIG_MAX_LENGTH}</div>
                </div>
                <div class="history-form-field">
                  <label class="history-form-label">Note to Pharmacist</label>
                  <input
                    class="history-form-input"
                    type="text"
                    maxLength=${NOTE_TO_PHARMACIST_MAX_LENGTH}
                    value=${noteToPharmacist}
                    onInput=${(e) => setNoteToPharmacist(e.target.value)}
                    placeholder="Optional"
                  />
                  <div class="char-counter${noteToPharmacist.length > NOTE_TO_PHARMACIST_MAX_LENGTH - 30 ? noteToPharmacist.length > NOTE_TO_PHARMACIST_MAX_LENGTH ? ' over-limit' : ' near-limit' : ''}">${noteToPharmacist.length} / ${NOTE_TO_PHARMACIST_MAX_LENGTH}</div>
                </div>
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Pharmacy</label>
                  <input
                    type="text"
                    class="history-form-input"
                    value=${pharmacyQuery}
                    onInput=${handlePharmacyInput}
                    onFocus=${() => { if (!pharmacyQuery && patientId && !selectedPharmacy) {
                      fetch(`${API_BASE}/search-pharmacies?patient_id=${encodeURIComponent(patientId)}`)
                        .then(r => r.json())
                        .then(d => setPharmacyResults(d.results || []))
                        .catch(() => {});
                    }}}
                    placeholder="Search pharmacies..."
                  />
                  ${pharmacySearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${pharmacyResults.length > 0 && !selectedPharmacy && html`
                    <div class="history-search-dropdown">
                      ${pharmacyResults.map(r => html`
                        <div
                          key=${r.ncpdp_id}
                          class="history-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handlePharmacySelect(r); }}
                        >
                          <div style="font-weight: 500;">${r.name || 'Unknown'}${r.preferred ? ' (preferred)' : ''}</div>
                          ${r.address && html`<div style="font-size: 12px; color: #666;">${r.address}</div>`}
                        </div>
                      `)}
                    </div>
                  `}
                  ${!pharmacySearching && pharmacySearched && pharmacyResults.length === 0 && pharmacyQuery.length >= 2 && html`
                    <div class="history-search-dropdown">
                      <div class="history-search-result search-no-results">No pharmacies found</div>
                    </div>
                  `}
                </div>
                <div class="history-form-field">
                  <label class="history-form-label">Substitutions</label>
                  <div class="allergy-severity">
                    <button type="button" class="task-quick-btn${substitutions ? ' active' : ''}" onClick=${() => setSubstitutions(true)}>Allowed</button>
                    <button type="button" class="task-quick-btn${!substitutions ? ' active' : ''}" onClick=${() => setSubstitutions(false)}>Not Allowed</button>
                  </div>
                </div>
              </div>
            `;})()}
            ${REFILL_TABS.has(activeTab) && !selectedFdb && html`
              <div class="history-form-field">
                <label class="history-form-label">Select medication to ${activeTab === 'refill' ? 'refill' : 'adjust'}</label>
                ${refillLoading
                  ? html`<span class="diag-search-spinner">Loading medications...</span>`
                  : refillMeds.length > 0
                    ? html`<select class="history-form-input" onChange=${handleRefillSelect}>
                        <option value="">Choose a medication...</option>
                        ${refillMeds.map((item, i) => html`<option key=${i} value=${i}>${item.medication_name}</option>`)}
                      </select>`
                    : html`<span class="removal-empty">No active medications</span>`
                }
              </div>
            `}
            ${activeTab === 'lab_order' && html`
              <div class="order-form">
                <div class="history-form-field">
                  <label class="history-form-label">Lab Partner</label>
                  <select class="history-form-input" value=${labPartnerId} onChange=${handleLabPartnerChange}>
                    <option value="">Select a lab partner...</option>
                    ${labPartners.map(p => html`
                      <option key=${p.id} value=${p.id}>${p.name}</option>
                    `)}
                  </select>
                </div>
                ${labPartnerId && html`
                  <div class="history-form-field" style="position: relative;">
                    <label class="history-form-label">Tests</label>
                    <input
                      ref=${labTestInputRef}
                      type="text"
                      class="history-form-input"
                      value=${labTestQuery}
                      onInput=${handleLabTestInput}
                      placeholder="Search tests..."
                    />
                    ${labTestSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                    ${labTestResults.length > 0 && html`
                      <div class="history-search-dropdown">
                        ${labTestResults.map(t => html`
                          <div
                            key=${t.order_code}
                            class="history-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleLabTestSelect(t); }}
                          >${t.order_name}${t.order_code ? ` (${t.order_code})` : ''}</div>
                        `)}
                      </div>
                    `}
                    ${!labTestSearching && labTestSearched && labTestResults.length === 0 && labTestQuery.length >= 2 && html`
                      <div class="history-search-dropdown">
                        <div class="history-search-result search-no-results">No tests found</div>
                      </div>
                    `}
                  </div>
                  ${selectedTests.length > 0 && html`
                    <div class="lab-selected-tests">
                      ${selectedTests.map(t => html`
                        <span class="lab-test-chip" key=${t.order_code}>
                          ${t.order_name}
                          <button type="button" class="lab-test-chip-remove" onClick=${() => handleLabTestRemove(t.order_code)}>×</button>
                        </span>
                      `)}
                    </div>
                  `}
                `}
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Diagnoses</label>
                  <input
                    ref=${diagInputRef}
                    class="history-form-input"
                    type="text"
                    value=${diagQuery}
                    onInput=${handleDiagInput}
                    onFocus=${() => setDiagFocused(true)}
                    onBlur=${() => setTimeout(() => setDiagFocused(false), 150)}
                    placeholder="Search diagnoses..."
                  />
                  ${diagSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${diagResults.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${diagResults.map(d => html`
                        <div
                          key=${d.code}
                          class="history-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleDiagSelect(d); }}
                        >${d.formatted_code || d.code} — ${d.display}</div>
                      `)}
                    </div>
                  `}
                  ${!diagSearching && diagSearched && diagResults.length === 0 && diagQuery.length >= 2 && html`
                    <div class="history-search-dropdown">
                      <div class="history-search-result search-no-results">No diagnoses found</div>
                    </div>
                  `}
                  ${diagFocused && !diagQuery && diagSuggestions.length > 0 && html`
                    <div class="history-search-dropdown">
                      <div class="diag-suggestion-header">Patient conditions</div>
                      ${diagSuggestions.map(d => html`
                        <div
                          key=${d.code}
                          class="history-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleDiagSelect(d); }}
                        >${d.formatted_code || d.code} — ${d.display}</div>
                      `)}
                    </div>
                  `}
                </div>
                ${selectedDiagnoses.length > 0 && html`
                  <div class="lab-selected-tests">
                    ${selectedDiagnoses.map(d => html`
                      <span class="lab-test-chip" key=${d.code}>
                        ${d.formatted_code || d.code}
                        <button type="button" class="lab-test-chip-remove" onClick=${() => handleDiagRemove(d.code)}>×</button>
                      </span>
                    `)}
                  </div>
                `}
                <div class="history-form-field">
                  <label class="history-form-label">Fasting</label>
                  <div class="allergy-severity">
                    <button type="button" class="task-quick-btn${!labFasting ? ' active' : ''}" onClick=${() => setLabFasting(false)}>Not Required</button>
                    <button type="button" class="task-quick-btn${labFasting ? ' active' : ''}" onClick=${() => setLabFasting(true)}>Required</button>
                  </div>
                </div>
                <div class="history-form-field">
                  <label class="history-form-label">Comment</label>
                  <input
                    class="history-form-input"
                    type="text"
                    maxLength=128
                    value=${labComment}
                    onInput=${(e) => setLabComment(e.target.value)}
                    placeholder="Optional"
                  />
                  <div class="char-counter${labComment.length > 110 ? labComment.length > 128 ? ' over-limit' : ' near-limit' : ''}">${labComment.length} / 128</div>
                </div>
              </div>
            `}
            ${activeTab === 'imaging_order' && html`
              <div class="order-form">
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Imaging</label>
                  <input
                    ref=${imagingInputRef}
                    type="text"
                    class="history-form-input"
                    value=${imagingQuery}
                    onInput=${handleImagingInput}
                    placeholder="Search imaging..."
                  />
                  ${imagingSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${imagingResults.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${imagingResults.map((r, i) => html`
                        <div key=${i} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleImagingSelect(r); }}>${r.display}</div>
                      `)}
                    </div>
                  `}
                  ${!imagingSearching && imagingSearched && imagingResults.length === 0 && imagingQuery.length >= 2 && html`
                    <div class="history-search-dropdown"><div class="history-search-result search-no-results">No imaging codes found</div></div>
                  `}
                </div>
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Diagnoses</label>
                  <input
                    ref=${imagingDiagInputRef}
                    class="history-form-input"
                    type="text"
                    value=${imagingDiagQuery}
                    onInput=${handleImagingDiagInput}
                    onFocus=${() => setImagingDiagFocused(true)}
                    onBlur=${() => setTimeout(() => setImagingDiagFocused(false), 150)}
                    placeholder="Search diagnoses..."
                  />
                  ${imagingDiagSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${imagingDiagResults.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${imagingDiagResults.map(d => html`
                        <div key=${d.code} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleImagingDiagSelect(d); }}>${d.formatted_code || d.code} — ${d.display}</div>
                      `)}
                    </div>
                  `}
                  ${!imagingDiagSearching && imagingDiagSearched && imagingDiagResults.length === 0 && imagingDiagQuery.length >= 2 && html`
                    <div class="history-search-dropdown"><div class="history-search-result search-no-results">No diagnoses found</div></div>
                  `}
                  ${imagingDiagFocused && !imagingDiagQuery && imagingDiagSuggestions.length > 0 && html`
                    <div class="history-search-dropdown">
                      <div class="diag-suggestion-header">Patient conditions</div>
                      ${imagingDiagSuggestions.map(d => html`
                        <div key=${d.code} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleImagingDiagSelect(d); }}>${d.formatted_code || d.code} — ${d.display}</div>
                      `)}
                    </div>
                  `}
                </div>
                ${imagingDiagnoses.length > 0 && html`
                  <div class="lab-selected-tests">
                    ${imagingDiagnoses.map(d => html`
                      <span class="lab-test-chip" key=${d.code}>
                        ${d.formatted_code || d.code}
                        <button type="button" class="lab-test-chip-remove" onClick=${() => handleImagingDiagRemove(d.code)}>×</button>
                      </span>
                    `)}
                  </div>
                `}
                <div class="history-form-field">
                  <label class="history-form-label">Order Details</label>
                  <input class="history-form-input" type="text" maxLength=1024 value=${imagingDetails} onInput=${(e) => setImagingDetails(e.target.value)} placeholder="Optional" />
                  <div class="char-counter${imagingDetails.length > 900 ? imagingDetails.length > 1024 ? ' over-limit' : ' near-limit' : ''}">${imagingDetails.length} / 1024</div>
                </div>
                <div class="history-form-field">
                  <label class="history-form-label">Comment</label>
                  <input class="history-form-input" type="text" maxLength=1024 value=${imagingComment} onInput=${(e) => setImagingComment(e.target.value)} placeholder="Optional" />
                  <div class="char-counter${imagingComment.length > 900 ? imagingComment.length > 1024 ? ' over-limit' : ' near-limit' : ''}">${imagingComment.length} / 1024</div>
                </div>
                <div class="history-form-field">
                  <label class="history-form-label">Priority</label>
                  <div class="allergy-severity">
                    <button type="button" class="task-quick-btn${imagingPriority === 'Routine' ? ' active' : ''}" onClick=${() => setImagingPriority('Routine')}>Routine</button>
                    <button type="button" class="task-quick-btn${imagingPriority === 'Urgent' ? ' active' : ''}" onClick=${() => setImagingPriority('Urgent')}>Urgent</button>
                  </div>
                </div>
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Ordering Provider</label>
                  <input
                    type="text"
                    class="history-form-input"
                    value=${providerQuery || orderingProviderName}
                    onInput=${handleProviderInput}
                    onFocus=${() => setProviderDropdownOpen(true)}
                    onBlur=${() => setTimeout(() => setProviderDropdownOpen(false), 200)}
                    placeholder="Search providers..."
                  />
                  ${providerDropdownOpen && filteredProviders.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${filteredProviders.map(p => html`
                        <div key=${p.id} class="history-search-result${p.id === orderingProviderId ? ' selected' : ''}" onMouseDown=${(e) => { e.preventDefault(); handleProviderSelect(p); }}>${p.label}</div>
                      `)}
                    </div>
                  `}
                  ${providerDropdownOpen && providerQuery && filteredProviders.length === 0 && html`
                    <div class="history-search-dropdown"><div class="history-search-result search-no-results">No providers found</div></div>
                  `}
                </div>
                <div class="history-form-field" style="position: relative;">
                  <label class="history-form-label">Imaging Center</label>
                  <input
                    ref=${centerInputRef}
                    type="text"
                    class="history-form-input"
                    value=${centerQuery || selectedCenterName}
                    onInput=${handleCenterInput}
                    placeholder="Search imaging centers..."
                  />
                  ${centerSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                  ${centerResults.length > 0 && html`
                    <div class="history-search-dropdown">
                      ${centerResults.map((r, i) => html`
                        <div key=${i} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleCenterSelect(r); }}>
                          <div style="font-weight:600">${r.name}</div>
                          ${r.description && html`<div style="font-size:12px;color:#888">${r.description}</div>`}
                        </div>
                      `)}
                    </div>
                  `}
                  ${!centerSearching && centerSearched && centerResults.length === 0 && centerQuery.length >= 2 && html`
                    <div class="history-search-dropdown"><div class="history-search-result search-no-results">No imaging centers found</div></div>
                  `}
                </div>
              </div>
            `}
            ${activeTab === 'refer' && html`
              <div class="order-form">
                <div class="history-form-field">
                  <label class="history-form-label">Refer To</label>
                  <div class="refer-token-input" style="position: relative;" onClick=${() => referProviderInputRef.current && referProviderInputRef.current.focus()}>
                    ${ICON_SEARCH}
                    ${referProviderDisplay ? html`
                      <span class="refer-token-chip" title=${referProviderDisplay}>
                        <span class="refer-token-text">${referProviderDisplay}</span>
                        <button type="button" onClick=${(e) => { e.stopPropagation(); setReferProvider(null); setReferProviderDisplay(''); setReferProviderQuery(''); }}>×</button>
                      </span>
                    ` : html`
                      <input
                        ref=${referProviderInputRef}
                        type="text"
                        value=${referProviderQuery}
                        onInput=${handleReferProviderInput}
                        onBlur=${() => setTimeout(() => { setReferProviderResults([]); setReferProviderSearched(false); }, 150)}
                        placeholder="Search providers..."
                      />
                    `}
                    ${referProviderSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                    ${referProviderResults.length > 0 && html`
                      <div class="history-search-dropdown">
                        ${referProviderResults.map((r, i) => html`
                          <div key=${i} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleReferProviderSelect(r); }}>
                            <div style="font-weight:600">${r.name}</div>
                            ${r.description && html`<div style="font-size:12px;color:#888">${r.description}</div>`}
                          </div>
                        `)}
                      </div>
                    `}
                    ${!referProviderSearching && referProviderSearched && referProviderResults.length === 0 && referProviderQuery.length >= 2 && html`
                      <div class="history-search-dropdown"><div class="history-search-result search-no-results">No providers found</div></div>
                    `}
                  </div>
                </div>
                <div class="refer-grid2">
                  <div class="history-form-field">
                    <label class="history-form-label">Indications</label>
                    <div class="refer-token-input" style="position: relative;" onClick=${() => referDiagInputRef.current && referDiagInputRef.current.focus()}>
                      ${ICON_SEARCH}
                      ${referDiagnoses.map(d => {
                        const label = (d.formatted_code || d.code) + (d.display && d.display !== (d.formatted_code || d.code) ? ` — ${d.display}` : '');
                        return html`
                          <span class="refer-token-chip" key=${d.code} title=${label}>
                            <span class="refer-token-text">${label}</span>
                            <button type="button" onClick=${(e) => { e.stopPropagation(); handleReferDiagRemove(d.code); }}>×</button>
                          </span>
                        `;
                      })}
                      ${referDiagnoses.length < 2 && html`
                        <input
                          ref=${referDiagInputRef}
                          type="text"
                          value=${referDiagQuery}
                          onInput=${handleReferDiagInput}
                          onFocus=${() => setReferDiagFocused(true)}
                          onBlur=${() => setTimeout(() => setReferDiagFocused(false), 150)}
                          placeholder=${referDiagnoses.length ? '' : 'Search diagnoses...'}
                        />
                      `}
                      ${referDiagSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                      ${referDiagResults.length > 0 && html`
                        <div class="history-search-dropdown">
                          ${referDiagResults.map(d => html`
                            <div key=${d.code} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleReferDiagSelect(d); }}>${d.formatted_code || d.code} — ${d.display}</div>
                          `)}
                        </div>
                      `}
                      ${!referDiagSearching && referDiagSearched && referDiagResults.length === 0 && referDiagQuery.length >= 2 && html`
                        <div class="history-search-dropdown"><div class="history-search-result search-no-results">No diagnoses found</div></div>
                      `}
                      ${referDiagFocused && !referDiagQuery && (noteDiagSuggestions.length > 0 || referDiagSuggestions.length > 0) && html`
                        <div class="history-search-dropdown">
                          ${noteDiagSuggestions.length > 0 && html`
                            <div class="diag-suggestion-header">From this note</div>
                            ${noteDiagSuggestions.map(d => html`
                              <div key=${`note-${d.code}`} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleReferDiagSelect(d); }}>${d.formatted_code || d.code} — ${d.display}</div>
                            `)}
                          `}
                          ${referDiagSuggestions.length > 0 && html`
                            <div class="diag-suggestion-header">Patient conditions</div>
                            ${referDiagSuggestions.map(d => html`
                              <div key=${`cond-${d.code}`} class="history-search-result" onMouseDown=${(e) => { e.preventDefault(); handleReferDiagSelect(d); }}>${d.formatted_code || d.code} — ${d.display}</div>
                            `)}
                          `}
                        </div>
                      `}
                    </div>
                  </div>
                  <div class="history-form-field">
                    <label class="history-form-label">Clinical Question</label>
                    <select class="history-form-input" value=${referClinicalQuestion} onChange=${(e) => setReferClinicalQuestion(e.target.value)}>
                      <option value="">Select...</option>
                      ${CLINICAL_QUESTIONS.map(q => html`
                        <option key=${q} value=${q}>${q}</option>
                      `)}
                    </select>
                  </div>
                </div>
                <div class="history-form-field">
                  <label class="history-form-label">Notes to Specialist</label>
                  <textarea class="history-form-textarea" rows="2" value=${referNotesToSpecialist} onInput=${(e) => setReferNotesToSpecialist(e.target.value)} placeholder="Required" />
                </div>
                ${(referPriorityOpen || referPriority) && html`
                  <div class="history-form-field">
                    <label class="history-form-label">Priority</label>
                    <div class="refer-priority">
                      <button type="button" class="refer-pill${referPriority === 'Routine' ? ' active' : ''}" onClick=${() => setReferPriority(referPriority === 'Routine' ? '' : 'Routine')}>Routine</button>
                      <button type="button" class="refer-pill${referPriority === 'Urgent' ? ' active' : ''}" onClick=${() => setReferPriority(referPriority === 'Urgent' ? '' : 'Urgent')}>Urgent</button>
                    </div>
                  </div>
                `}
                ${(referCommentOpen || referComment) && html`
                  <div class="history-form-field">
                    <label class="history-form-label">Comment</label>
                    <textarea class="history-form-textarea" rows="2" value=${referComment} onInput=${(e) => setReferComment(e.target.value)} placeholder="Optional" />
                  </div>
                `}
                ${(!(referPriorityOpen || referPriority) || !(referCommentOpen || referComment)) && html`
                  <div class="refer-disclosures">
                    ${!(referPriorityOpen || referPriority) && html`<button type="button" class="refer-add-pill" onClick=${() => setReferPriorityOpen(true)}>+ Add priority</button>`}
                    ${!(referCommentOpen || referComment) && html`<button type="button" class="refer-add-pill" onClick=${() => setReferCommentOpen(true)}>+ Add comment</button>`}
                  </div>
                `}
              </div>
            `}
            <div class="questionnaire-form-actions">
              <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
              <button
                type="button"
                class="form-btn form-btn-save"
                disabled=${(() => {
                  // Length-based gating (applies to whichever tab is active).
                  if (sig.length > SIG_MAX_LENGTH) return true;
                  if (noteToPharmacist.length > NOTE_TO_PHARMACIST_MAX_LENGTH) return true;
                  if (labComment.length > 128) return true;
                  if (imagingDetails.length > 1024) return true;
                  if (imagingComment.length > 1024) return true;
                  // Required-field gating for Rx tabs. The same predicate runs
                  // in summary.js (Approve / Add Now) and in
                  // _rx_validation.py on the server. Saving an Rx card with
                  // missing fields previously slipped past every layer and
                  // failed at REVIEW after the user thought it succeeded.
                  if (RX_TAB_KEYS.has(activeTab)) {
                    if (!selectedFdb) return true;
                    if (!sig) return true;
                    const qtyNum = quantity === '' || quantity == null ? null : Number(quantity);
                    const qtyStr = String(quantity ?? '').trim();
                    if (qtyNum == null || Number.isNaN(qtyNum) || qtyNum <= 0
                        || (qtyStr.includes('.') && (qtyStr.endsWith('0') || qtyStr.endsWith('.')))) {
                      return true;
                    }
                    if (!typeToDispense) return true;
                    const refillsNum = refills === '' || refills == null ? null : Number(refills);
                    if (refillsNum == null || Number.isNaN(refillsNum) || !Number.isInteger(refillsNum)
                        || refillsNum < REFILLS_MIN || refillsNum > REFILLS_MAX) {
                      return true;
                    }
                    // Days supply: optional, but if present must be a
                    // non-negative integer (mirrors _validate_days_supply).
                    if (daysSupply !== '' && daysSupply != null) {
                      const daysNum = Number(daysSupply);
                      if (!Number.isFinite(daysNum) || !Number.isInteger(daysNum) || daysNum < 0) return true;
                    }
                    // substitutions is a boolean toggle in the UI (true -> "allowed"),
                    // so it can't be missing — no extra check needed here.
                  }
                  return false;
                })()}
                onClick=${handleSave}
              >Save</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // View mode.
  const badgeLabel = BADGE_LABELS[command.command_type] || 'Order';

  if (command.command_type === 'prescribe' && command.display) {
    const d = command.data;
    const detailParts = [];
    if (d.quantity_to_dispense) {
      const typeLabel = d.type_to_dispense_label || '';
      detailParts.push(`Qty: ${d.quantity_to_dispense}${typeLabel ? ` ${typeLabel}` : ''}`);
    }
    if (d.days_supply) detailParts.push(`${d.days_supply}d supply`);
    if (d.refills != null && d.refills !== '') detailParts.push(`${d.refills} refill${d.refills > 1 ? 's' : ''}`);
    return html`
      <div>
        <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
          <div class="order-view">
            <span class="command-type-label">${badgeLabel}</span>
            <div class="order-view-name">${command.display}${aiPending ? AI_SPARKLE : ''}</div>
            ${d.sig && html`<div class="order-view-sig">Sig: ${d.sig}</div>`}
            ${detailParts.length > 0 && html`<div class="order-view-details">${detailParts.join(' · ')}</div>`}
          </div>
        </div>
        ${interactionWarning && html`<${InteractionWarningInline} warning=${interactionWarning} />`}
      </div>
    `;
  }

  if (command.command_type === 'refer') {
    const d = command.data;
    const codes = d.diagnosis_codes || [];
    const displays = d.diagnosis_displays || [];
    const formatted = d.diagnosis_formatted || [];
    const indications = codes.map((code, i) => {
      const fmt = formatted[i] || code;
      const name = displays[i] || '';
      return name && name !== fmt ? `${name} (${fmt})` : fmt;
    }).filter(Boolean);
    const indicationsLine = indications.join(', ');
    return html`
      <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
        <div class="order-view">
          <span class="command-type-label">Refer</span>
          <div class="order-view-name">${command.display || 'Referral'}${aiPending ? AI_SPARKLE : ''}</div>
          ${indicationsLine && html`<div class="order-view-meta">${indicationsLine}</div>`}
          ${d.notes_to_specialist && html`<div class="order-view-meta">${d.notes_to_specialist}</div>`}
        </div>
      </div>
    `;
  }

  if (command.command_type === 'imaging_order') {
    const d = command.data;
    const detailParts = [];
    if (d.additional_details) detailParts.push(d.additional_details);
    if (d.priority) detailParts.push(d.priority);
    if (d.ordering_provider_name) detailParts.push(d.ordering_provider_name);
    if (d.service_provider_name) detailParts.push(d.service_provider_name);
    return html`
      <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
        <div class="order-view">
          <span class="command-type-label">${badgeLabel}</span>
          <div class="order-view-name">${command.display}${aiPending ? AI_SPARKLE : ''}</div>
          ${detailParts.length > 0 && html`<div class="order-view-details">${detailParts.join(' · ')}</div>`}
        </div>
      </div>
    `;
  }

  return html`
    <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
      <div class="order-view">
        <span class="command-type-label">${badgeLabel}</span>
        <div class="order-view-name">${command.display}${aiPending ? AI_SPARKLE : ''}</div>
      </div>
    </div>
  `;
}
