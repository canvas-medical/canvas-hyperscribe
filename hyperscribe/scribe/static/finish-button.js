import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);
const CONFIRM_TIMEOUT_MS = 5000;

export function FinishRecordingButton({ onFinish }) {
  const [confirming, setConfirming] = useState(false);
  const timer = useRef(null);

  const handleClick = useCallback(() => {
    if (confirming) {
      clearTimeout(timer.current);
      setConfirming(false);
      onFinish();
    } else {
      setConfirming(true);
      timer.current = setTimeout(() => setConfirming(false), CONFIRM_TIMEOUT_MS);
    }
  }, [confirming, onFinish]);

  return html`
    <button class="finish-btn ${confirming ? 'confirming' : ''}" onClick=${handleClick}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
      ${confirming ? 'Confirm done recording?' : 'Finish'}
    </button>
  `;
}
