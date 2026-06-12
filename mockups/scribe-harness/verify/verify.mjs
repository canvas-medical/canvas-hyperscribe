/*
 * verify.mjs — headless fidelity gate for the Scribe UI harness.
 *
 * Boots the harness in real Chrome and asserts that the shipping components
 * actually render: every scenario mounts without page errors, every gallery
 * card is the standard 720px width, and the search dropdowns populate (which
 * proves the mock-fetch response shapes match what the components read).
 *
 * Prereqs: the harness server must be running from the repo root
 *   (python3 -m http.server 8000), then:  cd verify && npm install && npm run verify
 *
 * Uses the installed Google Chrome via Playwright's `channel: 'chrome'`, so no
 * machine-specific browser path is needed. Override with BASE_URL / CHANNEL.
 */
import { chromium } from 'playwright-core';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000/mockups/scribe-harness/';
const CHANNEL = process.env.CHANNEL || 'chrome';

const fail = [];
const ok = (cond, msg) => { console.log(`  ${cond ? '✅' : '❌'} ${msg}`); if (!cond) fail.push(msg); };

const browser = await chromium.launch({ channel: CHANNEL, headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1700, height: 1100 });

const pageErrors = [];
const unrouted = new Set();
page.on('pageerror', (e) => pageErrors.push(String(e)));
page.on('console', (m) => { const t = m.text(); if (t.includes('no route for')) unrouted.add(t.replace(/.*no route for /, '').split(' ')[0]); });

await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(1500);

// 1. Every scenario mounts with no page errors.
console.log('\nScenarios:');
const ids = await page.evaluate(() => window.__scenarioIds);
for (const id of ids) {
  pageErrors.length = 0;
  await page.evaluate((i) => window.__mount(i), id);
  await page.waitForTimeout(700);
  const len = await page.evaluate(() => document.getElementById('app').innerText.length);
  ok(len > 100 && pageErrors.length === 0, `scenario "${id}" renders (len ${len}, ${pageErrors.length} errors)`);
}

// 2. Gallery: all cards at the standard 720px viewport width.
console.log('\nComponent gallery:');
await page.evaluate(() => window.__showGallery());
await page.waitForTimeout(1500);
const widths = await page.evaluate(() => [...new Set([...document.querySelectorAll('.gallery-state')].map((c) => Math.round(c.getBoundingClientRect().width)))]);
const cardCount = await page.evaluate(() => document.querySelectorAll('.gallery-state').length);
ok(cardCount > 25, `${cardCount} gallery cards rendered`);
ok(widths.length === 1 && widths[0] === 720, `all cards are 720px wide (got ${JSON.stringify(widths)})`);

// 2b. Header-states page: every state mounts and the key header markers appear.
console.log('\nHeader states:');
pageErrors.length = 0;
await page.evaluate(() => window.__showHeader());
await page.waitForTimeout(2500);
const hdr = await page.evaluate(() => {
  const cards = [...document.querySelectorAll('.header-state')];
  const has = (sel) => !!document.querySelector(`.header-surface ${sel}`);
  // Each card should end with the SUBJECTIVE header (context) but hide its body.
  const subjectiveContext = cards.every((c) => {
    const first = c.querySelector('.header-surface .summary-body .summary-section');
    if (!first) return false;
    const title = first.querySelector('.section-title')?.textContent.trim();
    const bodyHidden = getComputedStyle(first.querySelector('.section-body')).display === 'none';
    return title === 'SUBJECTIVE' && bodyHidden;
  });
  // Transcript entries shown as example context on the recording card.
  const recCard = document.getElementById('h-recording');
  return {
    count: cards.length,
    amendingPill: [...document.querySelectorAll('.summary-status-pill--amending')].length,
    finalizedPill: [...document.querySelectorAll('.summary-status-pill--finalized')].length,
    banners: document.querySelectorAll('.header-surface .readonly-banner').length,
    recControls: has('.recording-controls-inline'),
    generateBanner: has('.summary-generate-banner'),
    subjectiveContext,
    recTranscript: recCard ? recCard.querySelectorAll('.transcript-entry').length : 0,
    // feat/canvas-scribe relocated this into the top bar (label-first, switch-last):
    // class is now `.hide-rejected-label--top-bar`. Accept either, for resilience.
    reviewToggle: !!document.querySelector('#h-review .hide-rejected-label--top-bar, #h-review .hide-rejected-toggle'),
  };
});
ok(hdr.count === 10, `10 header-state cards (got ${hdr.count})`);
ok(hdr.amendingPill >= 1 && hdr.finalizedPill >= 1, `amending + finalized pills present`);
ok(hdr.banners >= 2, `read-only banners present (${hdr.banners})`);
ok(hdr.recControls && hdr.generateBanner, `recording controls + generate banner present`);
ok(hdr.subjectiveContext, `every card ends with the SUBJECTIVE context line (body hidden)`);
ok(hdr.recTranscript > 0, `recording card shows the example transcript (${hdr.recTranscript} entries)`);
ok(hdr.reviewToggle, `review card shows the Hide Rejected Recommendations toggle`);
ok(pageErrors.length === 0, `header page renders with ${pageErrors.length} page errors`);

// 3. Search dropdowns populate (proves mock-fetch shapes match the components).
//    Back to the gallery — the header section above navigated away from it.
console.log('\nSearch dropdowns:');
await page.evaluate(() => window.__showGallery());
await page.waitForTimeout(1500);
async function search(label, scopeSel, text) {
  const input = await page.$(`${scopeSel} input.history-form-input[type="text"], ${scopeSel} input[type="text"]`);
  if (!input) { ok(false, `${label}: input found`); return; }
  await input.click(); await input.type(text, { delay: 30 });
  await page.waitForTimeout(1200);
  const n = await page.evaluate((s) => document.querySelectorAll(`${s} .history-search-result`).length, scopeSel);
  ok(n > 0, `${label}: "${text}" → ${n} result(s)`);
}
await search('history (medical)', '#g-HistoryEntryRow', 'hyper');
await search('diagnose', '#g-DiagnoseRow', 'diab');
await search('allergy', '#g-AllergyRow', 'pen');

// 4. No unrouted endpoints surfaced during the run.
console.log('\nCoverage:');
ok(unrouted.size === 0, `no unrouted endpoints (${[...unrouted].join(', ') || 'none'})`);

await browser.close();
console.log(`\n${fail.length === 0 ? 'PASS ✅ — harness is high-fidelity' : `FAIL ❌ — ${fail.length} issue(s)`}`);
process.exit(fail.length === 0 ? 0 : 1);
