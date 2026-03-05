import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { SubjectiveSection } from '/plugin-io/api/hyperscribe/scribe/static/subjective-section.js';
import { ObjectiveSection } from '/plugin-io/api/hyperscribe/scribe/static/objective-section.js';
import { AssessmentPlanSection } from '/plugin-io/api/hyperscribe/scribe/static/assessment-plan-section.js';

const html = htm.bind(h);

// Mock data — will be replaced with real data from the API
const MOCK_DATA = {
  subjective: `Patient is a 40-year-old female presenting with a two-week history of recurrent right-sided headaches. Headaches worsen in the afternoon and are associated with photosensitivity and occasional nausea. Denies visual changes, aura, or recent trauma. Reports partial relief with over-the-counter ibuprofen, though headaches recur daily.`,
  objective: [
    'General: Alert, oriented, in no acute distress',
    'HEENT: No tenderness over sinuses, no papilledema on fundoscopic exam',
    'Neuro: Cranial nerves II-XII intact, no focal deficits, normal gait',
    'Vitals: BP 122/78, HR 72, Temp 98.6\u00B0F',
  ],
  assessmentAndPlan: {
    diagnosis: 'Migraine without aura (G43.009)',
    items: [
      'Start sumatriptan 50mg PO at onset of headache, may repeat x1 after 2 hours if needed. Max 200mg/24hrs.',
      'Order MRI brain without contrast to rule out structural etiology',
      'Refer to neurology (Dr. Patel) for comprehensive headache evaluation',
    ],
  },
};

export function Summary({ noteDbid }) {
  return html`
    <div class="summary-container">
      <${SubjectiveSection} text=${MOCK_DATA.subjective} />
      <${ObjectiveSection} items=${MOCK_DATA.objective} />
      <${AssessmentPlanSection}
        diagnosis=${MOCK_DATA.assessmentAndPlan.diagnosis}
        items=${MOCK_DATA.assessmentAndPlan.items}
      />
    </div>
  `;
}
