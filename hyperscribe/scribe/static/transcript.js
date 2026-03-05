import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const MOCK_TRANSCRIPT = [
  { speaker: 'Dr. Smith', role: 'provider', time: '0:00', text: 'Good morning, Jane. How are you feeling today?' },
  { speaker: 'Patient', role: 'patient', time: '0:04', text: "Hi, Doctor. I've been having these really bad headaches for about two weeks now. They're mostly on the right side and they get worse in the afternoon." },
  { speaker: 'Dr. Smith', role: 'provider', time: '0:18', text: 'I see. Are you experiencing any nausea, sensitivity to light, or visual changes with these headaches?' },
  { speaker: 'Patient', role: 'patient', time: '0:26', text: "Yes, actually. I've noticed some light sensitivity and occasional nausea, especially when the headache is really bad. No visual changes though." },
  { speaker: 'Dr. Smith', role: 'provider', time: '0:40', text: 'Have you tried anything for the pain? Over-the-counter medications?' },
  { speaker: 'Patient', role: 'patient', time: '0:45', text: "I've been taking ibuprofen but it only helps a little. The headaches keep coming back." },
  { speaker: 'Dr. Smith', role: 'provider', time: '1:02', text: "Okay. I'd like to start you on sumatriptan for acute episodes and get an MRI to rule out any structural causes. I'm also going to refer you to Dr. Patel in neurology for a more comprehensive evaluation. Let's also order some basic bloodwork." },
];

function RecordingBanner() {
  return html`
    <div class="recording-banner">
      <span class="recording-dot"></span>
      <span>Recording in progress</span>
    </div>
  `;
}

function TranscriptEntry({ speaker, role, time, text }) {
  const initial = role === 'provider' ? 'Dr' : 'Pt';
  return html`
    <div class="transcript-entry">
      <div class="entry-avatar ${role}">${initial}</div>
      <div class="entry-content">
        <div class="entry-meta">
          <span class="entry-speaker">${speaker}</span>
          <span class="entry-time">${time}</span>
        </div>
        <p class="entry-text">${text}</p>
      </div>
    </div>
  `;
}

export function Scribe({ noteDbid }) {
  const [recording, setRecording] = useState(false);
  const [visibleCount, setVisibleCount] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (recording && visibleCount < MOCK_TRANSCRIPT.length) {
      timerRef.current = setTimeout(() => {
        setVisibleCount(c => c + 1);
      }, 1500);
    }
    return () => clearTimeout(timerRef.current);
  }, [recording, visibleCount]);

  const handleToggle = () => {
    if (!recording) {
      setVisibleCount(0);
    }
    setRecording(!recording);
  };

  const entries = MOCK_TRANSCRIPT.slice(0, visibleCount);

  return html`
    <div class="scribe-container">
      ${recording && html`<${RecordingBanner} />`}
      <div class="scribe-header">
        <h2>Scribe</h2>
      </div>
      <div class="record-area">
        <button
          class="record-btn ${recording ? 'recording' : ''}"
          onClick=${handleToggle}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            ${recording
              ? html`<rect x="6" y="6" width="12" height="12" rx="2" />`
              : html`<circle cx="12" cy="12" r="8" />`}
          </svg>
        </button>
        <span class="record-label">${recording ? 'Recording...' : 'Tap to record'}</span>
      </div>
      ${entries.length > 0 && html`
        <div class="transcript-list">
          ${entries.map((entry, i) => html`
            <${TranscriptEntry} key=${i} ...${entry} />
          `)}
        </div>
      `}
      ${!recording && entries.length === 0 && html`
        <p class="transcript-placeholder">Transcript content will appear here.</p>
      `}
    </div>
  `;
}
