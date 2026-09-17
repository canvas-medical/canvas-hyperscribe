#!/usr/bin/env python
"""Measure the questionnaire fill against labelled cases, using real Opus 5 calls.

This is a measurement run, not a pass/fail gate. It reports precision, recall, the
fabrication and denial-confusion counts, evidence integrity, run-to-run stability,
latency, tokens and cost. Thresholds get set from these numbers, not guessed ahead of
them.

Deliberately a script rather than a ``test_*.py`` under ``evaluations/``: the collection
hook at ``conftest.py:108`` pulls in the whole legacy ``Settings`` env for anything
matching its eval filenames, and this needs only ``ANTHROPIC_API_KEY``.

It drives the shipping code path. ``fill_questionnaires`` runs with a real client, so
chunking, cache warm-up, the fan-out, the grounding gate and ``build_fill_command_data``
all behave as they do in production. Only ``load_questionnaire`` is stubbed, because it is
the sole ORM touch.

    export ANTHROPIC_API_KEY=sk-ant-...
    uv run scripts/eval_questionnaire_fill.py                     # all cases, 1 run
    uv run scripts/eval_questionnaire_fill.py --runs 3            # stability
    uv run scripts/eval_questionnaire_fill.py --case never_discussed
    uv run scripts/eval_questionnaire_fill.py --dry-run           # no API calls
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from http import HTTPStatus
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# canvas_sdk's __init__ sets DJANGO_SETTINGS_MODULE, which the plugin's `logger` import
# needs before it will load. pytest gets this for free; a plain script has to ask.
import canvas_sdk  # noqa: E402,F401

from hyperscribe.scribe.backend.models import Transcript, TranscriptItem  # noqa: E402
from hyperscribe.scribe.recommendations import questionnaire_fill as qf  # noqa: E402

CASES_DIR = REPO / "evaluations" / "scribe" / "questionnaire_fill" / "cases"

# Claude Opus 5, $ per million tokens. Cache reads bill at 0.1x input, writes at 1.25x.
COST_INPUT = 5.00
COST_OUTPUT = 25.00
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25

# 30s is the hard Http.post wall. Anything past this is one slow response from failing.
WALL_SECONDS = 30.0
DANGER_SECONDS = 25.0

ANSWERED = ("answered", "denied")


# ── classification ────────────────────────────────────────────────────────────

FABRICATION = "fabrication"
DENIAL_CONFUSION = "denial_confusion"
BAND_ERROR = "band_error"
OVER_ABSTENTION = "over_abstention"
CORRECT = "correct"
WRONG_VALUE = "wrong_value"

# Ordered worst-first for reporting: the top two are the ones that can reach a signed note
# as a plausible-looking wrong answer.
SEVERITY = [FABRICATION, DENIAL_CONFUSION, BAND_ERROR, WRONG_VALUE, OVER_ABSTENTION, CORRECT]


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def classify(expected: dict[str, Any], actual: dict[str, Any] | None) -> tuple[str, str]:
    """Compare one question's ground truth against what the model produced.

    Returns (classification, detail). ``actual`` is None when the model abstained.
    """
    want = expected.get("status", "not_assessed")
    acceptable_statuses = expected.get("acceptable_statuses") or [want]

    if actual is None or actual["status"] == "not_assessed":
        if want == "not_assessed":
            return CORRECT, ""
        return OVER_ABSTENTION, f"expected {want}, abstained"

    got = actual["status"]

    # The model answered. Anything the transcript did not support is the dangerous class.
    if want == "not_assessed":
        kind = DENIAL_CONFUSION if got == "denied" else FABRICATION
        return kind, f"expected abstention, got {got}"

    if got not in acceptable_statuses:
        # answered-vs-denied disagreement where an answer was warranted either way
        return DENIAL_CONFUSION, f"expected {want}, got {got}"

    # Right call on whether it was discussed. Now: is the value right?
    if "option_dbid" in expected:
        acceptable = expected.get("acceptable_option_dbids") or [expected["option_dbid"]]
        chosen = actual.get("selected_option_dbid")
        if chosen not in acceptable:
            return BAND_ERROR, f"expected option {expected['option_dbid']}, got {chosen}"
        return CORRECT, "" if chosen == expected["option_dbid"] else f"acceptable neighbour {chosen}"

    if "option_dbids" in expected:
        want_set = set(expected["option_dbids"])
        got_set = set(actual.get("selected_option_dbids") or [])
        if got_set != want_set:
            return BAND_ERROR, f"expected {sorted(want_set)}, got {sorted(got_set)}"
        return CORRECT, ""

    if "value_contains" in expected:
        if _normalise(expected["value_contains"]) not in _normalise(str(actual.get("value") or "")):
            return WRONG_VALUE, f"{actual.get('value')!r} missing {expected['value_contains']!r}"
        return CORRECT, ""

    if "value" in expected:
        acceptable = expected.get("acceptable_values") or [expected["value"]]
        if str(actual.get("value") or "").strip() not in acceptable:
            return WRONG_VALUE, f"expected {expected['value']!r}, got {actual.get('value')!r}"
        return CORRECT, ""

    return CORRECT, ""


def evidence_integrity(actual: dict[str, Any], by_item_id: dict[str, str]) -> tuple[str, list[str]]:
    """Do the cited quotes actually appear in the turns they claim to come from?

    ``_apply_grounding_gate`` verifies only that the item_id exists, and with ``any()``, so
    one real id carries an item whose other citations are invented. This measures the size
    of that hole; nothing in production checks it.
    """
    problems: list[str] = []
    turns = actual.get("evidence") or []
    if not turns:
        return "none", ["no evidence cited"]
    verified = 0
    for turn in turns:
        item_id = turn.get("item_id")
        if item_id not in by_item_id:
            problems.append(f"item_id {item_id!r} not in transcript")
            continue
        if _normalise(turn.get("quote", "")) in _normalise(by_item_id[item_id]):
            verified += 1
        else:
            problems.append(f"quote not found in {item_id}: {turn.get('quote', '')[:60]!r}")
    if verified == len(turns):
        return "all", problems
    return ("some", problems) if verified else ("none", problems)


@contextmanager
def stubbed_questionnaire(definition: dict[str, Any]) -> Iterator[None]:
    """Swap out the one ORM touch for the duration of a fill.

    ``load_questionnaire`` is the only place ``fill_questionnaires`` reaches the database, so
    stubbing it is what lets the rest of the shipping path run untouched off a JSON case.
    """
    original = qf.load_questionnaire

    def loader(questionnaire_dbid: int) -> dict[str, Any]:
        return definition

    qf.load_questionnaire = loader
    try:
        yield
    finally:
        qf.load_questionnaire = original


# ── running one case ──────────────────────────────────────────────────────────


@dataclass
class RunResult:
    case_id: str
    classifications: dict[str, tuple[str, str]] = field(default_factory=dict)
    integrity: dict[str, tuple[str, list[str]]] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    evidence_turn_counts: dict[str, int] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)
    status: str = ""
    elapsed_s: float = 0.0
    error: str | None = None


def _fill_block(data: dict[str, Any], question_dbid: int) -> dict[str, Any] | None:
    for question in data.get("questions", []):
        if question["dbid"] != question_dbid:
            continue
        fill = question.get("fill")
        if not fill:
            return None
        selected = [r for r in question.get("responses", []) if r.get("selected")]
        return {
            "status": fill["status"],
            "confidence": fill.get("confidence"),
            "evidence": fill.get("evidence") or [],
            "selected_option_dbid": selected[0]["dbid"] if len(selected) == 1 else None,
            "selected_option_dbids": [r["dbid"] for r in selected],
            "value": selected[0]["value"] if selected else None,
        }
    return None


def run_case(case: dict[str, Any], api_key: str, model: str, effort: str) -> RunResult:
    definition = case["questionnaire"]
    transcript = Transcript(items=[TranscriptItem(**item) for item in case["transcript"]])
    by_item_id = {item["item_id"]: item["text"] for item in case["transcript"]}
    result = RunResult(case_id=case["id"])

    started = time.time()
    try:
        with stubbed_questionnaire(definition):
            outcomes, telemetry = qf.fill_questionnaires(
                [definition["questionnaire_dbid"]], transcript, api_key, model=model, effort=effort
            )
    except Exception as exc:  # noqa: BLE001 - a harness must report, not crash
        result.error = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        result.elapsed_s = time.time() - started

    result.telemetry = telemetry
    if not outcomes:
        result.error = "no outcome returned"
        return result
    outcome = outcomes[0]
    result.status = outcome.status
    if outcome.error:
        result.error = outcome.error
    if not outcome.data:
        return result

    for dbid_str, expected in case["expected"].items():
        dbid = int(dbid_str)
        actual = _fill_block(outcome.data, dbid)
        result.classifications[dbid_str] = classify(expected, actual)
        if actual and actual["status"] in ANSWERED:
            result.integrity[dbid_str] = evidence_integrity(actual, by_item_id)
            result.evidence_turn_counts[dbid_str] = len(actual["evidence"])
            chosen = actual.get("selected_option_dbid") or actual.get("selected_option_dbids") or actual.get("value")
            result.answers[dbid_str] = f"{actual['status']}:{chosen}"
        else:
            result.answers[dbid_str] = "not_assessed"
    return result


# ── reporting ─────────────────────────────────────────────────────────────────


def cost_of(telemetry: dict[str, Any]) -> float:
    million = 1_000_000
    uncached = int(telemetry.get("input_tokens", 0) or 0)
    output = int(telemetry.get("output_tokens", 0) or 0)
    reads = int(telemetry.get("cache_read_tokens", 0) or 0)
    writes = int(telemetry.get("cache_write_tokens", 0) or 0)
    return (
        uncached * COST_INPUT / million
        + output * COST_OUTPUT / million
        + reads * COST_INPUT * CACHE_READ_MULTIPLIER / million
        + writes * COST_INPUT * CACHE_WRITE_MULTIPLIER / million
    )


def report(all_runs: list[RunResult], runs_per_case: int) -> str:
    lines: list[str] = []
    add = lines.append

    add("# Questionnaire fill evaluation\n")
    add(f"Cases: {len({r.case_id for r in all_runs})} | runs per case: {runs_per_case} | total runs: {len(all_runs)}\n")

    # ── answer quality ──
    tally: dict[str, int] = dict.fromkeys(SEVERITY, 0)
    for run in all_runs:
        for kind, _ in run.classifications.values():
            tally[kind] = tally.get(kind, 0) + 1
    graded = sum(tally.values())

    add("## Answer quality\n")
    add("| Classification | Count | Share |")
    add("|---|---:|---:|")
    for kind in SEVERITY:
        share = f"{100 * tally[kind] / graded:.1f}%" if graded else "-"
        add(f"| {kind} | {tally[kind]} | {share} |")
    add("")

    blocking = tally[FABRICATION] + tally[DENIAL_CONFUSION]
    add(
        f"**Answers not supported by the transcript: {blocking}** "
        f"({tally[FABRICATION]} fabrication, {tally[DENIAL_CONFUSION]} denial confusion). "
        "This is the count that decides whether the feature is safe to write into a signed note.\n"
    )

    if blocking:
        add("### Unsupported answers, in detail\n")
        for run in all_runs:
            for dbid, (kind, detail) in run.classifications.items():
                if kind in (FABRICATION, DENIAL_CONFUSION):
                    add(f"- `{run.case_id}` q{dbid}: {kind} — {detail}")
        add("")

    # Wrong but grounded. Not release-blocking, but on a scored screener a band error still
    # moves the total, so it is worth reading rather than just counting.
    lesser = [
        (run.case_id, dbid, kind, detail)
        for run in all_runs
        for dbid, (kind, detail) in run.classifications.items()
        if kind in (BAND_ERROR, WRONG_VALUE, OVER_ABSTENTION)
    ]
    if lesser:
        add("### Grounded but wrong, and misses\n")
        for case_id, dbid, kind, detail in lesser:
            add(f"- `{case_id}` q{dbid}: {kind} — {detail}")
        add("")

    # ── evidence integrity ──
    integrity_tally: dict[str, int] = {"all": 0, "some": 0, "none": 0}
    integrity_problems: list[str] = []
    for run in all_runs:
        for dbid, (verdict, problems) in run.integrity.items():
            integrity_tally[verdict] += 1
            for problem in problems:
                integrity_problems.append(f"- `{run.case_id}` q{dbid}: {problem}")
    checked = sum(integrity_tally.values())

    add("## Evidence integrity\n")
    add(
        "Does each cited quote actually appear in the turn it claims to come from? "
        "`_apply_grounding_gate` checks only that the item_id exists, and with `any()`, so this "
        "is unguarded in production.\n"
    )
    add("| Verdict | Items |")
    add("|---|---:|")
    for verdict in ("all", "some", "none"):
        add(f"| quotes {verdict} verified | {integrity_tally[verdict]} |")
    add("")
    if checked:
        rate = 100 * integrity_tally["all"] / checked
        add(f"**Fully verified: {rate:.1f}%** of {checked} grounded answers.\n")
    if integrity_problems:
        add("<details><summary>Problems</summary>\n")
        lines.extend(integrity_problems[:40])
        add("\n</details>\n")

    # ── stability ──
    if runs_per_case > 1:
        add("## Run-to-run stability\n")
        add(
            "Adaptive thinking is nondeterministic and there is no temperature control, so the "
            "same transcript can produce different answers.\n"
        )
        add("| Case | Questions | Unstable |")
        add("|---|---:|---:|")
        by_case: dict[str, list[RunResult]] = {}
        for run in all_runs:
            by_case.setdefault(run.case_id, []).append(run)
        for case_id, runs in sorted(by_case.items()):
            keys = {k for r in runs for k in r.answers}
            unstable = [k for k in keys if len({r.answers.get(k) for r in runs}) > 1]
            add(f"| {case_id} | {len(keys)} | {len(unstable)} |")
        add("")

    # ── performance ──
    add("## Performance and cost\n")
    latencies = [r.elapsed_s for r in all_runs if not r.error]
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        add("| Metric | Value |")
        add("|---|---:|")
        add(f"| runs measured | {len(latencies)} |")
        add(f"| p50 wall time | {statistics.median(ordered):.1f}s |")
        add(f"| p95 wall time | {p95:.1f}s |")
        add(f"| max wall time | {max(ordered):.1f}s |")
        add(f"| runs over {DANGER_SECONDS:.0f}s | {sum(1 for x in ordered if x > DANGER_SECONDS)} |")
        add("")
        add(
            f"Wall time is the whole fill including the serial cache warm-up, so it exceeds any "
            f"single chunk. The {WALL_SECONDS:.0f}s limit applies per request, not per fill.\n"
        )

    total_cost = sum(cost_of(r.telemetry) for r in all_runs)
    reads = sum(r.telemetry.get("cache_read_tokens", 0) for r in all_runs)
    writes = sum(r.telemetry.get("cache_write_tokens", 0) for r in all_runs)
    uncached = sum(r.telemetry.get("input_tokens", 0) for r in all_runs)
    output = sum(r.telemetry.get("output_tokens", 0) for r in all_runs)

    add("| Tokens | Total |")
    add("|---|---:|")
    add(f"| uncached input | {uncached:,} |")
    add(f"| cache reads | {reads:,} |")
    add(f"| cache writes | {writes:,} |")
    add(f"| output | {output:,} |")
    add("")
    if reads + uncached:
        add(
            f"**Cache hit rate: {100 * reads / (reads + uncached):.1f}%** of input tokens served "
            "from cache. Zero on multi-chunk cases would mean the chunking is costing money "
            "rather than saving it.\n"
        )
    add(
        f"**Total spend this run: ${total_cost:.4f}** across {len(all_runs)} runs "
        f"(${total_cost / max(1, len(all_runs)):.4f} per fill).\n"
    )

    # ── per case ──
    add("## Per case\n")
    add("| Case | Status | Worst | Time | Cost | Probes |")
    add("|---|---|---|---:|---:|---|")
    for run in all_runs[:200]:
        kinds = [k for k, _ in run.classifications.values()]
        worst = next((k for k in SEVERITY if k in kinds), "-")
        add(
            f"| {run.case_id} | {run.error or run.status} | {worst} | "
            f"{run.elapsed_s:.1f}s | ${cost_of(run.telemetry):.4f} | "
            f"{run.telemetry.get('chunks', 0)} chunk(s) |"
        )
    add("")
    return "\n".join(lines)


# ── self-test ─────────────────────────────────────────────────────────────────


def self_test() -> int:
    """Prove the classifier and integrity checker can actually fail.

    A harness that reports success regardless is worse than no harness, and this costs
    nothing to run. Makes no API calls.
    """
    passed = failed = 0

    def check(label: str, got: Any, want: Any) -> None:
        nonlocal passed, failed
        if got == want:
            passed += 1
            print(f"  ok    {label}")
        else:
            failed += 1
            print(f"  FAIL  {label}: got {got!r}, want {want!r}")

    def answered(**kw: Any) -> dict[str, Any]:
        return {"status": "answered", "evidence": [], **kw}

    def denied(**kw: Any) -> dict[str, Any]:
        return {"status": "denied", "evidence": [], **kw}

    print("classification")
    check(
        "expected abstention, model answered -> fabrication",
        classify({"status": "not_assessed"}, answered(selected_option_dbid=101))[0],
        FABRICATION,
    )
    check(
        "expected abstention, model denied -> denial confusion",
        classify({"status": "not_assessed"}, denied(selected_option_dbid=100))[0],
        DENIAL_CONFUSION,
    )
    check("expected abstention, model abstained -> correct", classify({"status": "not_assessed"}, None)[0], CORRECT)
    check(
        "expected answer, model abstained -> over-abstention",
        classify({"status": "answered", "option_dbid": 101}, None)[0],
        OVER_ABSTENTION,
    )
    check(
        "wrong severity band -> band error",
        classify({"status": "answered", "option_dbid": 103}, answered(selected_option_dbid=100))[0],
        BAND_ERROR,
    )
    check(
        "acceptable neighbour band -> correct",
        classify(
            {"status": "answered", "option_dbid": 102, "acceptable_option_dbids": [101, 102]},
            answered(selected_option_dbid=101),
        )[0],
        CORRECT,
    )
    check(
        "multiselect, order-insensitive -> correct",
        classify({"status": "answered", "option_dbids": [201, 202]}, answered(selected_option_dbids=[202, 201]))[0],
        CORRECT,
    )
    check(
        "multiselect, one missing -> band error",
        classify({"status": "answered", "option_dbids": [201, 202]}, answered(selected_option_dbids=[201]))[0],
        BAND_ERROR,
    )
    check(
        "free text substring, punctuation-insensitive -> correct",
        classify({"status": "answered", "value_contains": "long haul"}, answered(value="Long-Haul  Truck Driver"))[0],
        CORRECT,
    )
    check(
        "integer rounded up -> wrong value",
        classify({"status": "answered", "value": "4"}, answered(value="5"))[0],
        WRONG_VALUE,
    )

    print("evidence integrity")
    turns = {"t1": "Maybe a few days here and there, not most days."}
    check(
        "quote present in the cited turn -> all",
        evidence_integrity({"evidence": [{"item_id": "t1", "quote": "a few days here and there"}]}, turns)[0],
        "all",
    )
    # The case the production gate cannot see: a real item_id carrying an invented quote.
    check(
        "invented quote on a real item_id -> none",
        evidence_integrity({"evidence": [{"item_id": "t1", "quote": "I feel hopeless every day"}]}, turns)[0],
        "none",
    )
    check(
        "one real citation, one invented -> some",
        evidence_integrity(
            {"evidence": [{"item_id": "t1", "quote": "a few days"}, {"item_id": "t9", "quote": "nope"}]}, turns
        )[0],
        "some",
    )
    check("no evidence cited -> none", evidence_integrity({"evidence": []}, turns)[0], "none")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


# ── failure injection ─────────────────────────────────────────────────────────


def inject() -> int:
    """Exercise the failure paths with stubbed responses and no API calls.

    A 429, a 5xx on the warm-up chunk, an unparseable body and a fabricated citation
    cannot be triggered on demand against the live API, but they are exactly the paths
    that decide whether a bad day degrades or corrupts. Structural assertions, so this one
    genuinely passes or fails.
    """
    from unittest.mock import MagicMock

    from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

    transcript = Transcript(
        items=[
            TranscriptItem(
                text="how often have you felt down?",
                speaker="DOCTOR",
                start_offset_ms=0,
                end_offset_ms=2000,
                item_id="t1",
            ),
            TranscriptItem(
                text="most days, honestly", speaker="PATIENT", start_offset_ms=2000, end_offset_ms=4000, item_id="t2"
            ),
        ]
    )

    def definition(count: int = 1) -> dict[str, Any]:
        return {
            "questionnaire_dbid": 1,
            "questionnaire_name": "Probe",
            "is_scored": False,
            "scoring_function_name": "",
            "questions": [
                {
                    "dbid": 10 + i,
                    "label": f"Q{i}",
                    "type": "SING",
                    "options": [
                        {"dbid": 100, "value": "Not at all", "code": "", "score_value": "0"},
                        {"dbid": 101, "value": "Nearly every day", "code": "", "score_value": "3"},
                    ],
                }
                for i in range(count)
            ],
        }

    def stub(payload: dict[str, Any] | None = None, code: Any = HTTPStatus.OK, raw: str | None = None) -> Any:
        client = MagicMock()
        client.last_usage = {}
        client.request.return_value = LlmResponse(
            code=code,
            response=raw if raw is not None else json.dumps(payload or {}),
            tokens=LlmTokens(prompt=0, generated=0),
        )
        return client

    def answer(item_id: str = "t2", quote: str = "most days, honestly") -> dict[str, Any]:
        return {
            "questionDbid": 10,
            "status": "answered",
            "selectedOptionDbid": 101,
            "evidence": [{"speaker": "patient", "quote": quote, "itemId": item_id}],
        }

    def run(count: int, factory: Any) -> tuple[Any, dict[str, Any]]:
        with stubbed_questionnaire(definition(count)):
            return qf.fill_questionnaires([1], transcript, "key", client_factory=factory)

    failed = 0

    def check(label: str, got: Any, want: Any) -> None:
        nonlocal failed
        if got == want:
            print(f"  ok    {label}")
        else:
            failed += 1
            print(f"  FAIL  {label}: got {got!r}, want {want!r}")

    original_sleep = qf.time.sleep
    qf.time.sleep = lambda _: None
    try:
        print("retry and abort")
        attempts = {"clients": 0}

        def rate_limited() -> Any:
            attempts["clients"] += 1
            return stub({}, code=HTTPStatus.TOO_MANY_REQUESTS)

        outcomes, _ = run(1, rate_limited)
        check("429 retries once then fails cleanly", outcomes[0].status, "failed")

        built: list[Any] = []

        def always_500() -> Any:
            client = stub({}, code=HTTPStatus.INTERNAL_SERVER_ERROR)
            built.append(client)
            return client

        outcomes, telemetry = run(20, always_500)  # 20 questions -> 4 chunks
        check("5xx on warm-up aborts the fan-out", telemetry["aborted"], True)
        check("5xx on warm-up builds 1 client, not 4", len(built), 1)

        print("grounding gate")
        outcomes, _ = run(1, lambda: stub({"questionnaireDbid": 1, "items": [answer(item_id="nope")]}))
        check("a citation to a nonexistent turn is dropped", outcomes[0].status, "abstained")

        outcomes, _ = run(1, lambda: stub({"questionnaireDbid": 1, "items": [answer(quote="I want to end my life")]}))
        # KNOWN GAP. The gate checks the item_id exists, never that the quote is in it.
        check("an invented quote on a real turn still passes (known gap)", outcomes[0].status, "filled")

        print("malformed responses")
        outcomes, _ = run(1, lambda: stub(raw="not json at all"))
        check("unparseable body fails rather than raising", outcomes[0].status, "failed")
        outcomes, _ = run(1, lambda: stub({"questionnaireDbid": 1, "items": []}))
        check(
            "no items returned reads as abstention with assessed 0",
            (outcomes[0].status, outcomes[0].assessed),
            ("abstained", 0),
        )
    finally:
        qf.time.sleep = original_sleep

    print(f"\n{failed} failure(s)")
    return 1 if failed else 0


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="case id; repeatable. Default: all.")
    parser.add_argument("--runs", type=int, default=1, help="repetitions per case (stability).")
    parser.add_argument("--model", default=qf.DEFAULT_MODEL)
    parser.add_argument("--effort", default=qf.DEFAULT_EFFORT)
    parser.add_argument("--out", type=Path, help="write the report here as well as stdout.")
    parser.add_argument("--dry-run", action="store_true", help="list cases; make no API calls.")
    parser.add_argument("--self-test", action="store_true", help="check the classifier itself; no API calls.")
    parser.add_argument("--inject", action="store_true", help="exercise failure paths; no API calls.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if args.inject:
        return inject()

    paths = sorted(CASES_DIR.glob("*.json"))
    cases = [json.loads(p.read_text()) for p in paths]
    if args.case:
        wanted = set(args.case)
        cases = [c for c in cases if c["id"] in wanted]
        missing = wanted - {c["id"] for c in cases}
        if missing:
            print(f"unknown case(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    if not cases:
        print(f"no cases found in {CASES_DIR}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"{len(cases)} case(s), {args.runs} run(s) each:\n")
        for case in cases:
            questions = len(case["questionnaire"]["questions"])
            chunks = len(qf.chunk_questions(case["questionnaire"]["questions"]))
            abstain = sum(1 for e in case["expected"].values() if e.get("status") == "not_assessed")
            print(f"  {case['id']:<32} {questions:>3}q  {chunks} chunk(s)  {abstain} must abstain   {case['probes']}")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 2

    all_runs: list[RunResult] = []
    for repetition in range(args.runs):
        for case in cases:
            label = f"[{repetition + 1}/{args.runs}] {case['id']}"
            print(f"{label} ... ", end="", flush=True)
            run = run_case(case, api_key, args.model, args.effort)
            all_runs.append(run)
            kinds = [k for k, _ in run.classifications.values()]
            worst = next((k for k in SEVERITY if k in kinds), "-")
            print(f"{run.error or run.status} | {worst} | {run.elapsed_s:.1f}s")

    text = report(all_runs, args.runs)
    print("\n" + text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
