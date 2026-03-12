import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

const ORDER_TABS = [
  { key: 'prescribe', label: 'Rx' },
  { key: 'lab_order', label: 'Lab' },
  { key: 'imaging_order', label: 'Imaging' },
];

const BADGE_LABELS = {
  prescribe: 'Rx',
  lab_order: 'Lab',
  imaging_order: 'Imaging',
};

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
    if (data.quantity_to_dispense) parts.push(`Qty: ${data.quantity_to_dispense}`);
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
  return '';
}

export function OrderRow({ command, commandIndex, onEdit, onDelete, readOnly, patientId, noteId, staffId, staffName }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);
  const [activeTab, setActiveTab] = useState(command.command_type || 'prescribe');

  // Rx state
  const [medQuery, setMedQuery] = useState(command.data.medication_text || '');
  const [medResults, setMedResults] = useState([]);
  const [medSearching, setMedSearching] = useState(false);
  const [medSearched, setMedSearched] = useState(false);
  const [selectedFdb, setSelectedFdb] = useState(command.data.fdb_code || null);
  const [selectedMedDisplay, setSelectedMedDisplay] = useState(command.data.medication_text || '');
  const [sig, setSig] = useState(command.data.sig || '');
  const [daysSupply, setDaysSupply] = useState(command.data.days_supply || '');
  const [quantity, setQuantity] = useState(command.data.quantity_to_dispense || '');
  const [refills, setRefills] = useState(command.data.refills || '');
  const [substitutions, setSubstitutions] = useState(command.data.substitutions !== 'not_allowed');
  const [noteToPharmacist, setNoteToPharmacist] = useState(command.data.note_to_pharmacist || '');

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

  // Load patient conditions when lab or imaging tab is active.
  useEffect(() => {
    if (activeTab !== 'lab_order' && activeTab !== 'imaging_order') return;
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

  // Close dropdown on outside click.
  useEffect(() => {
    if (!editing) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setMedResults([]);
        setLabTestResults([]);
        setDiagResults([]);
        setDiagFocused(false);
        setImagingResults([]);
        setImagingDiagResults([]);
        setImagingDiagFocused(false);
        setProviderResults([]);
        setCenterResults([]);
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
    setSelectedMedDisplay(val);
    debouncedMedSearch(val);
  };

  const handleMedSelect = (result) => {
    setSelectedFdb(result.fdb_code);
    setSelectedMedDisplay(result.description);
    setMedQuery(result.description);
    setMedResults([]);
    setMedSearched(false);
  };

  const handleSave = () => {
    let data = {};
    if (activeTab === 'prescribe') {
      if (!selectedMedDisplay.trim()) return;
      data = {
        fdb_code: selectedFdb || null,
        medication_text: selectedMedDisplay,
        sig,
        days_supply: daysSupply ? Number(daysSupply) : null,
        quantity_to_dispense: quantity ? Number(quantity) : null,
        refills: refills ? Number(refills) : null,
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
          <div class="order-form">
            ${activeTab === 'prescribe' && html`
              <div class="order-rx-form">
                <div class="medication-search-wrapper">
                  <div class="labeled-field" style="width:100%">
                    <span class="labeled-field-label">Medication</span>
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
                ${selectedFdb && html`<span class="medication-structured-badge">FDB: ${selectedFdb}</span>`}
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Qty</span>
                    <input class="labeled-field-input" type="number" value=${quantity} onInput=${(e) => setQuantity(e.target.value)} min="0" />
                  </div>
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Days</span>
                    <input class="labeled-field-input" type="number" value=${daysSupply} onInput=${(e) => setDaysSupply(e.target.value)} min="0" />
                  </div>
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Refills</span>
                    <input class="labeled-field-input" type="number" value=${refills} onInput=${(e) => setRefills(e.target.value)} min="0" />
                  </div>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Sig</span>
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
  return html`
    <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
      <span class="command-type-badge badge-${command.command_type}">${badgeLabel}</span>
      <span class="command-row-text">${command.display}</span>
    </div>
  `;
}
