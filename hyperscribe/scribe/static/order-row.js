import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

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
  { key: 'lab_order', label: 'Lab' },
  { key: 'imaging_order', label: 'Imaging' },
  { key: 'refer', label: 'Refer' },
];

const BADGE_LABELS = {
  prescribe: 'Rx',
  lab_order: 'Lab',
  imaging_order: 'Imaging',
  refer: 'Refer',
};

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
    const parts = [];
    if (data.refer_to_display) parts.push(data.refer_to_display);
    if (data.clinical_question) parts.push(data.clinical_question);
    if (data.priority) parts.push(data.priority);
    return parts.join(' | ') || '';
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

export function OrderRow({ command, commandIndex, onEdit, onDelete, readOnly, patientId, noteId, staffId, staffName, isRecommendation }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);
  const [activeTab, setActiveTab] = useState(command.command_type || 'prescribe');

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
  const [interactionWarning, setInteractionWarning] = useState(null);
  const [checkingInteractions, setCheckingInteractions] = useState(false);

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
  const [orderingProviderId, setOrderingProviderId] = useState(command.data.ordering_provider_id || staffId || '');
  const [orderingProviderName, setOrderingProviderName] = useState(command.data.ordering_provider_name || staffName || '');
  const [providerQuery, setProviderQuery] = useState('');
  const [providerResults, setProviderResults] = useState([]);
  const [providerSearching, setProviderSearching] = useState(false);
  const [providerSearched, setProviderSearched] = useState(false);
  const [centerQuery, setCenterQuery] = useState('');
  const [centerResults, setCenterResults] = useState([]);
  const [centerSearching, setCenterSearching] = useState(false);
  const [centerSearched, setCenterSearched] = useState(false);
  const [selectedCenter, setSelectedCenter] = useState(command.data.service_provider || null);
  const [selectedCenterName, setSelectedCenterName] = useState(command.data.service_provider_name || '');
  const imagingInputRef = useRef(null);
  const imagingDiagInputRef = useRef(null);
  const providerInputRef = useRef(null);
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
  const [referPriority, setReferPriority] = useState(command.data.priority || 'Routine');
  const [referNotesToSpecialist, setReferNotesToSpecialist] = useState(command.data.notes_to_specialist || '');
  const [referComment, setReferComment] = useState(command.data.comment || '');
  const referProviderInputRef = useRef(null);
  const referDiagInputRef = useRef(null);

  const medInputRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (editing && activeTab === 'prescribe' && medInputRef.current) {
      medInputRef.current.focus();
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
    if (labTestInputRef.current) labTestInputRef.current.focus();
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
    if (diagInputRef.current) diagInputRef.current.focus();
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
    if (imagingDiagInputRef.current) imagingDiagInputRef.current.focus();
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

  // Ordering provider search.
  const doProviderSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setProviderResults([]); setProviderSearched(false); return; }
    setProviderSearching(true);
    try {
      const res = await fetch(`${API_BASE}/ordering-providers?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      setProviderResults(data.providers || []);
    } catch (err) {
      setProviderResults([]);
    } finally {
      setProviderSearching(false);
      setProviderSearched(true);
    }
  }, []);

  const debouncedProviderSearch = useDebounce(doProviderSearch, DEBOUNCE_MS);

  const handleProviderInput = (e) => {
    const val = e.target.value;
    setProviderQuery(val);
    setOrderingProviderId('');
    setOrderingProviderName(val);
    debouncedProviderSearch(val);
  };

  const handleProviderSelect = (provider) => {
    setOrderingProviderId(provider.id);
    setOrderingProviderName(provider.label);
    setProviderQuery('');
    setProviderResults([]);
    setProviderSearched(false);
  };

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
    setReferProvider(null);
    setReferProviderDisplay(val);
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
    setReferDiagnoses([...referDiagnoses, diag]);
    setReferDiagQuery('');
    setReferDiagResults([]);
    setReferDiagSearched(false);
    if (referDiagInputRef.current) referDiagInputRef.current.focus();
  };

  const handleReferDiagRemove = (code) => {
    setReferDiagnoses(referDiagnoses.filter(d => d.code !== code));
  };

  const referDiagSuggestions = (() => {
    if (!referDiagQuery && patientConditions.length > 0) {
      const alreadySelected = new Set(referDiagnoses.map(d => d.code));
      return patientConditions.filter(c => !alreadySelected.has(c.code));
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
    if (activeTab === 'prescribe') {
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
      };
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
        priority: referPriority || 'Routine',
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

  if (editing) {
    return html`
      <div class="order-row editing" ref=${containerRef} onKeyDown=${handleKeyDown}>
        <div class="order-layout">
          ${!isRecommendation && html`
            <div class="order-tabs">
              ${ORDER_TABS.map(tab => html`
                <button
                  key=${tab.key}
                  type="button"
                  class="order-tab${activeTab === tab.key ? ' active' : ''}"
                  onClick=${() => setActiveTab(tab.key)}
                >${tab.label}</button>
              `)}
            </div>
          `}
          <div class="order-form">
            ${activeTab === 'prescribe' && html`
              <div class="order-rx-form">
                <div class="medication-search-wrapper">
                  <div class="labeled-field" style="width:100%">
                    <span class="labeled-field-label">Medication <span class="field-required">*</span></span>
                    <input
                      ref=${medInputRef}
                      type="text"
                      class="labeled-field-input"
                      value=${medQuery}
                      onInput=${handleMedInput}
                      placeholder="Search medications..."
                    />
                  </div>
                  ${medSearching && html`<span class="medication-search-spinner">Searching...</span>`}
                  ${medResults.length > 0 && html`
                    <div class="medication-search-dropdown">
                      ${medResults.map(r => html`
                        <div
                          key=${r.fdb_code}
                          class="medication-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleMedSelect(r); }}
                        >${r.description}</div>
                      `)}
                    </div>
                  `}
                  ${!medSearching && medSearched && medResults.length === 0 && medQuery.length >= 2 && html`
                    <div class="medication-search-dropdown">
                      <div class="medication-search-result search-no-results">No medications found</div>
                    </div>
                  `}
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:2">
                    <span class="labeled-field-label">Qty <span class="field-required">*</span></span>
                    <div style="display:flex;align-items:center;gap:4px">
                      <input class="labeled-field-input" style="flex:0 0 60px" type="number" value=${quantity} onInput=${(e) => setQuantity(e.target.value)} min="0" />
                      <span style="font-size:12px;color:#666">x</span>
                      <select class="labeled-field-input" style="flex:1;min-width:120px" value=${typeToDispense} onChange=${(e) => setTypeToDispense(e.target.value)}>
                        <option value="">—</option>
                        ${medQuantities.map(o => html`
                          <option key=${o.value} value=${o.value}>${o.label}</option>
                        `)}
                      </select>
                    </div>
                  </div>
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Days</span>
                    <input class="labeled-field-input" type="number" value=${daysSupply} onInput=${(e) => setDaysSupply(e.target.value)} min="0" />
                  </div>
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Refills <span class="field-required">*</span></span>
                    <input class="labeled-field-input" type="number" value=${refills} onInput=${(e) => setRefills(e.target.value)} min="0" />
                  </div>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Sig <span class="field-required">*</span></span>
                    <input class="labeled-field-input" type="text" value=${sig} onInput=${(e) => setSig(e.target.value)} />
                  </div>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Note to Pharmacist</span>
                    <input class="labeled-field-input" type="text" value=${noteToPharmacist} onInput=${(e) => setNoteToPharmacist(e.target.value)} />
                  </div>
                </div>
                <div class="order-rx-row">
                  <button type="button" class="task-quick-btn${substitutions ? ' active' : ''}" onClick=${() => setSubstitutions(true)}>Substitutions Allowed</button>
                  <button type="button" class="task-quick-btn${!substitutions ? ' active' : ''}" onClick=${() => setSubstitutions(false)}>Substitutions Not Allowed</button>
                </div>
              </div>
            `}
            ${activeTab === 'lab_order' && html`
              <div class="order-lab-form">
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Lab Partner</span>
                    <select class="labeled-field-input" value=${labPartnerId} onChange=${handleLabPartnerChange}>
                      <option value="">Select a lab partner...</option>
                      ${labPartners.map(p => html`
                        <option key=${p.id} value=${p.id}>${p.name}</option>
                      `)}
                    </select>
                  </div>
                </div>
                ${labPartnerId && html`
                  <div class="order-rx-row">
                    <div class="lab-test-search-wrapper" style="flex:1">
                      <div class="labeled-field" style="width:100%">
                        <span class="labeled-field-label">Tests</span>
                        <input
                          ref=${labTestInputRef}
                          type="text"
                          class="labeled-field-input"
                          value=${labTestQuery}
                          onInput=${handleLabTestInput}
                          placeholder="Search tests..."
                        />
                      </div>
                      ${labTestSearching && html`<span class="lab-test-search-spinner">Searching...</span>`}
                      ${labTestResults.length > 0 && html`
                        <div class="lab-test-search-dropdown">
                          ${labTestResults.map(t => html`
                            <div
                              key=${t.order_code}
                              class="lab-test-search-result"
                              onMouseDown=${(e) => { e.preventDefault(); handleLabTestSelect(t); }}
                            >${t.order_name}${t.order_code ? ` (${t.order_code})` : ''}</div>
                          `)}
                        </div>
                      `}
                      ${!labTestSearching && labTestSearched && labTestResults.length === 0 && labTestQuery.length >= 2 && html`
                        <div class="lab-test-search-dropdown">
                          <div class="lab-test-search-result search-no-results">No tests found</div>
                        </div>
                      `}
                    </div>
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
                <div class="order-rx-row">
                  <div class="diag-search-wrapper" style="flex:1">
                    <div class="labeled-field" style="width:100%">
                      <span class="labeled-field-label">Dx</span>
                      <input
                        ref=${diagInputRef}
                        class="labeled-field-input"
                        type="text"
                        value=${diagQuery}
                        onInput=${handleDiagInput}
                        onFocus=${() => setDiagFocused(true)}
                        onBlur=${() => setTimeout(() => setDiagFocused(false), 150)}
                        placeholder="Search diagnoses..."
                      />
                    </div>
                    ${diagSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                    ${diagResults.length > 0 && html`
                      <div class="diag-search-dropdown">
                        ${diagResults.map(d => html`
                          <div
                            key=${d.code}
                            class="diag-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleDiagSelect(d); }}
                          >${d.formatted_code || d.code} — ${d.display}</div>
                        `)}
                      </div>
                    `}
                    ${!diagSearching && diagSearched && diagResults.length === 0 && diagQuery.length >= 2 && html`
                      <div class="diag-search-dropdown">
                        <div class="diag-search-result search-no-results">No diagnoses found</div>
                      </div>
                    `}
                    ${diagFocused && !diagQuery && diagSuggestions.length > 0 && html`
                      <div class="diag-search-dropdown">
                        <div class="diag-suggestion-header">Patient conditions</div>
                        ${diagSuggestions.map(d => html`
                          <div
                            key=${d.code}
                            class="diag-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleDiagSelect(d); }}
                          >${d.formatted_code || d.code} — ${d.display}</div>
                        `)}
                      </div>
                    `}
                  </div>
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
                <div class="order-rx-row">
                  <button type="button" class="task-quick-btn${!labFasting ? ' active' : ''}" onClick=${() => setLabFasting(false)}>Fasting Not Required</button>
                  <button type="button" class="task-quick-btn${labFasting ? ' active' : ''}" onClick=${() => setLabFasting(true)}>Fasting Required</button>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Comment</span>
                    <input
                      class="labeled-field-input"
                      type="text"
                      value=${labComment}
                      onInput=${(e) => setLabComment(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            `}
            ${activeTab === 'imaging_order' && html`
              <div class="order-imaging-form">
                <div class="imaging-search-wrapper">
                  <div class="labeled-field" style="width:100%">
                    <span class="labeled-field-label">Imaging</span>
                    <input
                      ref=${imagingInputRef}
                      type="text"
                      class="labeled-field-input"
                      value=${imagingQuery}
                      onInput=${handleImagingInput}
                      placeholder="Search imaging..."
                    />
                  </div>
                  ${imagingSearching && html`<span class="imaging-search-spinner">Searching...</span>`}
                  ${imagingResults.length > 0 && html`
                    <div class="imaging-search-dropdown">
                      ${imagingResults.map((r, i) => html`
                        <div
                          key=${i}
                          class="imaging-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleImagingSelect(r); }}
                        >${r.display}</div>
                      `)}
                    </div>
                  `}
                  ${!imagingSearching && imagingSearched && imagingResults.length === 0 && imagingQuery.length >= 2 && html`
                    <div class="imaging-search-dropdown">
                      <div class="imaging-search-result search-no-results">No imaging codes found</div>
                    </div>
                  `}
                </div>
                <div class="order-rx-row">
                  <div class="diag-search-wrapper" style="flex:1">
                    <div class="labeled-field" style="width:100%">
                      <span class="labeled-field-label">Dx</span>
                      <input
                        ref=${imagingDiagInputRef}
                        class="labeled-field-input"
                        type="text"
                        value=${imagingDiagQuery}
                        onInput=${handleImagingDiagInput}
                        onFocus=${() => setImagingDiagFocused(true)}
                        onBlur=${() => setTimeout(() => setImagingDiagFocused(false), 150)}
                        placeholder="Search diagnoses..."
                      />
                    </div>
                    ${imagingDiagSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                    ${imagingDiagResults.length > 0 && html`
                      <div class="diag-search-dropdown">
                        ${imagingDiagResults.map(d => html`
                          <div
                            key=${d.code}
                            class="diag-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleImagingDiagSelect(d); }}
                          >${d.formatted_code || d.code} — ${d.display}</div>
                        `)}
                      </div>
                    `}
                    ${!imagingDiagSearching && imagingDiagSearched && imagingDiagResults.length === 0 && imagingDiagQuery.length >= 2 && html`
                      <div class="diag-search-dropdown">
                        <div class="diag-search-result search-no-results">No diagnoses found</div>
                      </div>
                    `}
                    ${imagingDiagFocused && !imagingDiagQuery && imagingDiagSuggestions.length > 0 && html`
                      <div class="diag-search-dropdown">
                        <div class="diag-suggestion-header">Patient conditions</div>
                        ${imagingDiagSuggestions.map(d => html`
                          <div
                            key=${d.code}
                            class="diag-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleImagingDiagSelect(d); }}
                          >${d.formatted_code || d.code} — ${d.display}</div>
                        `)}
                      </div>
                    `}
                  </div>
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
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Order Details</span>
                    <input
                      class="labeled-field-input"
                      type="text"
                      value=${imagingDetails}
                      onInput=${(e) => setImagingDetails(e.target.value)}
                    />
                  </div>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Comment</span>
                    <input
                      class="labeled-field-input"
                      type="text"
                      value=${imagingComment}
                      onInput=${(e) => setImagingComment(e.target.value)}
                    />
                  </div>
                </div>
                <div class="order-rx-row">
                  <button type="button" class="task-quick-btn${imagingPriority === 'Routine' ? ' active' : ''}" onClick=${() => setImagingPriority('Routine')}>Routine</button>
                  <button type="button" class="task-quick-btn${imagingPriority === 'Urgent' ? ' active' : ''}" onClick=${() => setImagingPriority('Urgent')}>Urgent</button>
                </div>
                <div class="imaging-search-wrapper">
                  <div class="labeled-field" style="width:100%">
                    <span class="labeled-field-label">Ordering Provider</span>
                    <input
                      ref=${providerInputRef}
                      type="text"
                      class="labeled-field-input"
                      value=${providerQuery || orderingProviderName}
                      onInput=${handleProviderInput}
                      onFocus=${() => { if (orderingProviderName) { setProviderQuery(orderingProviderName); debouncedProviderSearch(orderingProviderName); } }}
                      placeholder="Search providers..."
                    />
                  </div>
                  ${providerSearching && html`<span class="imaging-search-spinner">Searching...</span>`}
                  ${providerResults.length > 0 && html`
                    <div class="imaging-search-dropdown">
                      ${providerResults.map(p => html`
                        <div
                          key=${p.id}
                          class="imaging-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleProviderSelect(p); }}
                        >${p.label}</div>
                      `)}
                    </div>
                  `}
                  ${!providerSearching && providerSearched && providerResults.length === 0 && providerQuery.length >= 2 && html`
                    <div class="imaging-search-dropdown">
                      <div class="imaging-search-result search-no-results">No providers found</div>
                    </div>
                  `}
                </div>
                <div class="imaging-search-wrapper">
                  <div class="labeled-field" style="width:100%">
                    <span class="labeled-field-label">Imaging Center</span>
                    <input
                      ref=${centerInputRef}
                      type="text"
                      class="labeled-field-input"
                      value=${centerQuery || selectedCenterName}
                      onInput=${handleCenterInput}
                      placeholder="Search imaging centers..."
                    />
                  </div>
                  ${centerSearching && html`<span class="imaging-search-spinner">Searching...</span>`}
                  ${centerResults.length > 0 && html`
                    <div class="imaging-search-dropdown">
                      ${centerResults.map((r, i) => html`
                        <div
                          key=${i}
                          class="imaging-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleCenterSelect(r); }}
                        >
                          <div class="imaging-center-name">${r.name}</div>
                          ${r.description && html`<div class="imaging-center-desc">${r.description}</div>`}
                        </div>
                      `)}
                    </div>
                  `}
                  ${!centerSearching && centerSearched && centerResults.length === 0 && centerQuery.length >= 2 && html`
                    <div class="imaging-search-dropdown">
                      <div class="imaging-search-result search-no-results">No imaging centers found</div>
                    </div>
                  `}
                </div>
              </div>
            `}
            ${activeTab === 'refer' && html`
              <div class="order-refer-form">
                <div class="imaging-search-wrapper">
                  <div class="labeled-field" style="width:100%">
                    <span class="labeled-field-label">Refer To</span>
                    <input
                      ref=${referProviderInputRef}
                      type="text"
                      class="labeled-field-input"
                      value=${referProviderQuery || referProviderDisplay}
                      onInput=${handleReferProviderInput}
                      placeholder="Search by name, specialty, or practice..."
                    />
                  </div>
                  ${referProviderSearching && html`<span class="imaging-search-spinner">Searching...</span>`}
                  ${referProviderResults.length > 0 && html`
                    <div class="imaging-search-dropdown">
                      ${referProviderResults.map((r, i) => html`
                        <div
                          key=${i}
                          class="imaging-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleReferProviderSelect(r); }}
                        >
                          <div class="imaging-center-name">${r.name}</div>
                          ${r.description && html`<div class="imaging-center-desc">${r.description}</div>`}
                        </div>
                      `)}
                    </div>
                  `}
                  ${!referProviderSearching && referProviderSearched && referProviderResults.length === 0 && referProviderQuery.length >= 2 && html`
                    <div class="imaging-search-dropdown">
                      <div class="imaging-search-result search-no-results">No providers found</div>
                    </div>
                  `}
                </div>
                <div class="order-rx-row">
                  <div class="diag-search-wrapper" style="flex:1">
                    <div class="labeled-field" style="width:100%">
                      <span class="labeled-field-label">Indications</span>
                      <input
                        ref=${referDiagInputRef}
                        class="labeled-field-input"
                        type="text"
                        value=${referDiagQuery}
                        onInput=${handleReferDiagInput}
                        onFocus=${() => setReferDiagFocused(true)}
                        onBlur=${() => setTimeout(() => setReferDiagFocused(false), 150)}
                        placeholder="Search diagnoses..."
                      />
                    </div>
                    ${referDiagSearching && html`<span class="diag-search-spinner">Searching...</span>`}
                    ${referDiagResults.length > 0 && html`
                      <div class="diag-search-dropdown">
                        ${referDiagResults.map(d => html`
                          <div
                            key=${d.code}
                            class="diag-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleReferDiagSelect(d); }}
                          >${d.formatted_code || d.code} — ${d.display}</div>
                        `)}
                      </div>
                    `}
                    ${!referDiagSearching && referDiagSearched && referDiagResults.length === 0 && referDiagQuery.length >= 2 && html`
                      <div class="diag-search-dropdown">
                        <div class="diag-search-result search-no-results">No diagnoses found</div>
                      </div>
                    `}
                    ${referDiagFocused && !referDiagQuery && referDiagSuggestions.length > 0 && html`
                      <div class="diag-search-dropdown">
                        <div class="diag-suggestion-header">Patient conditions</div>
                        ${referDiagSuggestions.map(d => html`
                          <div
                            key=${d.code}
                            class="diag-search-result"
                            onMouseDown=${(e) => { e.preventDefault(); handleReferDiagSelect(d); }}
                          >${d.formatted_code || d.code} — ${d.display}</div>
                        `)}
                      </div>
                    `}
                  </div>
                </div>
                ${referDiagnoses.length > 0 && html`
                  <div class="lab-selected-tests">
                    ${referDiagnoses.map(d => html`
                      <span class="lab-test-chip" key=${d.code}>
                        ${d.formatted_code || d.code}
                        <button type="button" class="lab-test-chip-remove" onClick=${() => handleReferDiagRemove(d.code)}>×</button>
                      </span>
                    `)}
                  </div>
                `}
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Clinical Question</span>
                    <select class="labeled-field-input" value=${referClinicalQuestion} onChange=${(e) => setReferClinicalQuestion(e.target.value)}>
                      <option value="">—</option>
                      ${CLINICAL_QUESTIONS.map(q => html`
                        <option key=${q} value=${q}>${q}</option>
                      `)}
                    </select>
                  </div>
                </div>
                <div class="order-rx-row">
                  <button type="button" class="task-quick-btn${referPriority === 'Routine' ? ' active' : ''}" onClick=${() => setReferPriority('Routine')}>Routine</button>
                  <button type="button" class="task-quick-btn${referPriority === 'Urgent' ? ' active' : ''}" onClick=${() => setReferPriority('Urgent')}>Urgent</button>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Notes to Specialist</span>
                    <textarea
                      class="labeled-field-input"
                      rows="4"
                      value=${referNotesToSpecialist}
                      onInput=${(e) => setReferNotesToSpecialist(e.target.value)}
                    />
                  </div>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Comment</span>
                    <textarea
                      class="labeled-field-input"
                      rows="4"
                      value=${referComment}
                      onInput=${(e) => setReferComment(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            `}
            <div class="command-row-actions">
              <button class="edit-btn" onClick=${handleSave}>Save</button>
              <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
              <button class="delete-btn" onClick=${() => onDelete(commandIndex)}>Delete</button>
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
    const hasFdb = !!d.fdb_code;
    return html`
      <div>
        <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;min-width:0">
            <div class="subsection-title">Rx</div>
            <div style="display:flex;align-items:center;gap:8px">
              <span class="medication-row-text">${command.display}</span>
              ${hasFdb
                ? html`<span class="medication-structured-badge">Structured</span>`
                : html`<span class="medication-unstructured-badge">Unstructured</span>`
              }
            </div>
            ${d.sig && html`<span class="medication-sig-text" style="margin-left:4px">Sig: ${d.sig}</span>`}
            ${detailParts.length > 0 && html`<span class="medication-sig-text" style="margin-left:4px">${detailParts.join(' · ')}</span>`}
          </div>
        </div>
        ${interactionWarning && html`<${InteractionWarningInline} warning=${interactionWarning} />`}
      </div>
    `;
  }

  if (command.command_type === 'refer') {
    const d = command.data;
    const hasProvider = !!d.service_provider;
    const detailParts = [];
    if (d.clinical_question) detailParts.push(d.clinical_question);
    if (d.priority) detailParts.push(d.priority);
    if (d.notes_to_specialist) detailParts.push(d.notes_to_specialist);
    return html`
      <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
        <div style="display:flex;flex-direction:column;gap:2px;flex:1;min-width:0">
          <div class="subsection-title">Refer</div>
          <div style="display:flex;align-items:center;gap:8px">
            <span class="medication-row-text">${command.display || 'Referral'}</span>
            ${hasProvider
              ? html`<span class="medication-structured-badge">Matched</span>`
              : html`<span class="medication-unstructured-badge">Incomplete</span>`
            }
          </div>
          ${detailParts.length > 0 && html`<span class="medication-sig-text" style="margin-left:4px">${detailParts.join(' · ')}</span>`}
        </div>
      </div>
    `;
  }

  if (command.command_type === 'imaging_order') {
    const d = command.data;
    const hasCenter = !!d.service_provider;
    const detailParts = [];
    if (d.additional_details) detailParts.push(d.additional_details);
    if (d.priority) detailParts.push(d.priority);
    if (d.ordering_provider_name) detailParts.push(d.ordering_provider_name);
    if (d.service_provider_name) detailParts.push(d.service_provider_name);
    return html`
      <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
        <div style="display:flex;flex-direction:column;gap:2px;flex:1;min-width:0">
          <div class="subsection-title">${badgeLabel}</div>
          <div style="display:flex;align-items:center;gap:8px">
            <span class="medication-row-text">${command.display}</span>
            ${!hasCenter && html`<span class="medication-unstructured-badge">Incomplete</span>`}
          </div>
          ${detailParts.length > 0 && html`<span class="medication-sig-text" style="margin-left:4px">${detailParts.join(' · ')}</span>`}
        </div>
      </div>
    `;
  }

  return html`
    <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
      <div class="subsection-title">${badgeLabel}</div>
      <span class="command-row-text">${command.display}</span>
    </div>
  `;
}
