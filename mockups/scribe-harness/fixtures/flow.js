/*
 * flow.js — guided end-to-end walkthroughs of the Scribe experience.
 *
 * Each flow is an ordered list of steps; every step mounts one of the named
 * scenarios (from scenarios.js) into the real <Scribe> surface and shows a
 * caption describing that moment in the journey. The harness renders a stepper
 * (tabs + prev/next + step pills) above the surface. The mounted surface is
 * live, so within any step you can still click into the real components.
 */
export const FLOWS = [
  {
    id: 'ai',
    label: 'AI Scribe',
    steps: [
      { scenarioId: 'start', title: 'Start',
        caption: 'The clinician opens the Scribe tab. No visit type or mode is selected yet, so Start AI Scribe and Manual are disabled. Choosing a visit template enables them.' },
      { scenarioId: 'ai-recording', title: 'Recording',
        caption: 'After picking a template and tapping Start AI Scribe, audio is captured. The transcript streams in live — the dimmed last line is a not-yet-final “listening” partial.' },
      { scenarioId: 'ai-paused', title: 'Paused',
        caption: 'The clinician pauses capture mid-visit. The transcript so far is preserved; Resume reconnects and continues.' },
      { scenarioId: 'empty', title: 'Generate',
        caption: 'Recording is finished. The clinician generates a structured summary from the transcript (the Generate Summary button is live here).' },
      { scenarioId: 'review-all', title: 'Review',
        caption: 'The generated summary appears as editable commands across the SOAP sections plus the charge matrix. The clinician reviews, edits, and accepts recommendations before approving.' },
      { scenarioId: 'amending', title: 'Amend',
        caption: 'After approving and signing, the clinician reopens the note to amend it. Documented commands in editable sections can be changed; brand-new commands can be added.' },
    ],
  },
  {
    id: 'manual',
    label: 'Manual',
    steps: [
      { scenarioId: 'start', title: 'Start',
        caption: 'Same entry point — the clinician opens the Scribe tab and chooses a visit template.' },
      { scenarioId: 'manual', title: 'Manual charting',
        caption: 'Instead of AI Scribe, the clinician taps Manual. Standard sections are seeded for direct charting and the Approve action in the footer is available right away — no recording or generation step.' },
    ],
  },
];

export const flowById = (id) => FLOWS.find((f) => f.id === id) || FLOWS[0];
