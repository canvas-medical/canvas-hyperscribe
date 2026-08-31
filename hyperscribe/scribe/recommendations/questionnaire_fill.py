"""Draft questionnaire answers from a visit transcript.

Two constraints shape everything here.

**Grounding.** The model may only answer when the transcript explicitly supports it, and
must attach the verbatim turns it relied on. ``_apply_grounding_gate`` drops anything whose
evidence does not resolve to a real transcript item, so an ungrounded guess never reaches
the chart. "Denied" stays distinct from "not discussed" — silence is never a negative.

**The 30-second wall.** ``canvas_sdk.utils.http.Http`` hardcodes a 30s timeout on every
POST with no per-request override, and a timeout surfaces as an HTTP 400 rather than an
exception, so a slow call fails silently. Latency tracks output and thinking tokens, both
of which scale with the number of judgments in one call, so questionnaires are split into
small chunks. Chunking repeats the transcript on every call, which is why the transcript
block is cached: without it the input cost would multiply by the chunk count.
"""

from __future__ import annotations

import json
import random
import time
from http import HTTPStatus
from typing import Any, Callable

from logger import log

from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.commands.commands.questionnaire.question import ResponseOption
from canvas_sdk.utils.http import ThreadPoolExecutor
from canvas_sdk.v1.data.questionnaire import Questionnaire as QuestionnaireModel

from hyperscribe.scribe.backend.models import Transcript
from hyperscribe.scribe.recommendations._llm_client import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    FAILURE_TRUNCATED,
    ScribeLlmAnthropic,
    make_fill_client,
)
from hyperscribe.scribe.recommendations.schemas import QuestionnaireFillResult, QuestionnaireItemFill

# Questions per request. Chosen so PHQ-2, AUDIT-C and GAD-7 stay single-call while PHQ-9
# splits in two and a long intake splits into many, keeping every request well inside the
# 30s wall.
CHUNK_SIZE = 6
SINGLE_CALL_MAX = 8

# Above this many characters of transcript, chunk harder. Question count alone is not a
# good enough proxy for latency, because a long transcript adds prefill time on top of the
# generation time the question count drives. Measured against a 43k-character, 47-minute
# visit: 8 questions took 24s locally and 29s on the instance, one second inside the wall;
# 6 took 20s; 4 took 15s and 13s. The instance runs consistently slower than a local call,
# so the budget has to leave room for it. Chunking more costs almost nothing, because every
# chunk after the first reads the cached transcript at a tenth of the input price.
LONG_TRANSCRIPT_CHARS = 20_000
LONG_CHUNK_SIZE = 4

# Anthropic rate limits, not local CPU, are what bounds this.
MAX_WORKERS = 4

# The transcript is block 1: block 0 is the system prompt and block 2 the chunk
# definition. Marking block 1 caches system + transcript and leaves the per-chunk part
# out of the cached prefix.
TRANSCRIPT_BLOCK_INDEX = 1

_RETRYABLE = (HTTPStatus.TOO_MANY_REQUESTS,)

_TYPE_LABELS = {
    ResponseOption.TYPE_TEXT: "free text (one written answer)",
    ResponseOption.TYPE_INTEGER: "integer (a single whole number)",
    ResponseOption.TYPE_RADIO: "single choice (pick exactly one option)",
    ResponseOption.TYPE_CHECKBOX: "multiple choice (pick every option that applies)",
}

_SYSTEM_PROMPT = """You are a clinical documentation assistant. You draft answers to a structured questionnaire from \
the transcript of a single patient encounter. Your output is a DRAFT for clinician review.

TWO RULES THAT OVERRIDE EVERYTHING ELSE:
1. Evidence or abstain. Answer a question ONLY when the transcript explicitly supports it, and attach the verbatim \
transcript turn(s) as evidence, each with the itemId it came from. If the transcript does not address a question, \
set status "not_assessed" and leave it blank. Never infer, assume, estimate, or round up.
2. "Denied" is not "not discussed". If the respondent explicitly declines or denies, set status "denied" (and for \
single/multiple choice select the option that records the denial). A topic that simply never came up is \
"not_assessed" - never read silence as a denial.

The respondent (patient), not the provider, must be the one affirming or denying. A bare "yes"/"no" is only \
interpretable together with the provider's question, so include both turns as evidence.

BY QUESTION TYPE:
- single choice: set selectedOptionDbid to exactly one option's dbid, or null.
- multiple choice: set selectedOptionDbids to the dbids of every option the respondent affirmed (may be empty).
- free text: set value to a grounded verbatim span, or null.
- integer: set value to the whole number the respondent stated, as a string, or null.

Return one item per question you answer or that is explicitly denied. Omit questions the transcript does not address."""


def _ensure_str(value: Any) -> str:
    """None becomes empty string; 0 and False keep their stringified form.

    Questionnaire scoring metadata uses integer 0 to mean "Not at all", so the falsy
    ``or ""`` idiom would silently destroy a real score.
    """
    return "" if value is None else str(value)


def resolve_questionnaire_definition(q_obj: Any) -> dict[str, Any]:
    """Full definition for a questionnaire: name, scoring metadata, questions, options.

    Single source of truth for this shape. ``session_view._resolve_questionnaire`` and the
    fill both need it, and when they built it separately they drifted — the fill's copy
    dropped ``code`` and ``score_value``, which is why a filled card could not compute a
    PHQ-9 score.
    """
    command = QuestionnaireCommand(questionnaire_id=str(q_obj.id), note_uuid="", command_uuid="")
    questions: list[dict[str, Any]] = []
    for question in command.questions:
        options = [
            {
                "dbid": option.dbid,
                "value": option.name,
                "code": _ensure_str(getattr(option, "code", None)),
                "score_value": _ensure_str(getattr(option, "value", None)),
            }
            for option in question.options
        ]
        questions.append({"dbid": int(question.id), "label": question.label, "type": question.type, "options": options})
    scoring_function_name = getattr(q_obj, "scoring_function_name", "") or ""
    return {
        "questionnaire_dbid": q_obj.dbid,
        "questionnaire_name": q_obj.name,
        "is_scored": bool(scoring_function_name),
        "scoring_function_name": scoring_function_name,
        "questions": questions,
    }


def load_questionnaire(questionnaire_dbid: int) -> dict[str, Any]:
    """Fetch and resolve one questionnaire by dbid."""
    return resolve_questionnaire_definition(QuestionnaireModel.objects.get(dbid=questionnaire_dbid))


def chunk_questions(questions: list[dict[str, Any]], transcript_chars: int = 0) -> list[list[dict[str, Any]]]:
    """Split a question list into per-request chunks.

    Short questionnaires run whole so they pay no cache-warm-up penalty; longer ones split
    so no single request approaches the 30s wall. Past ``LONG_TRANSCRIPT_CHARS`` the
    shortcut is withdrawn and the chunks get smaller, because on a long visit even eight
    questions in one call runs to the wall.

    ``transcript_chars`` defaults to 0 so a caller that only wants the question-count
    behaviour, and every existing test, gets it unchanged.
    """
    long_visit = transcript_chars >= LONG_TRANSCRIPT_CHARS
    chunk_size = LONG_CHUNK_SIZE if long_visit else CHUNK_SIZE
    single_call_max = LONG_CHUNK_SIZE if long_visit else SINGLE_CALL_MAX
    if len(questions) <= single_call_max:
        return [questions] if questions else []
    return [questions[i : i + chunk_size] for i in range(0, len(questions), chunk_size)]


def _render_transcript(transcript: Transcript) -> str:
    turns = [
        {"item_id": item.item_id, "speaker": item.speaker, "text": item.text}
        for item in transcript.items
        if item.text.strip()
    ]
    return json.dumps(turns, indent=1)


def _render_definition(name: str, questions: list[dict[str, Any]]) -> str:
    rendered = [
        {
            "question_dbid": question["dbid"],
            "prompt": question["label"],
            "type": _TYPE_LABELS.get(question["type"], str(question["type"])),
            "options": [{"option_dbid": o["dbid"], "label": o["value"]} for o in question["options"]],
        }
        for question in questions
    ]
    return json.dumps({"questionnaire": name, "questions": rendered}, indent=1)


def _apply_grounding_gate(result: QuestionnaireFillResult, transcript: Transcript) -> QuestionnaireFillResult:
    # Enforce "evidence or abstain": an answered/denied item whose evidence does not resolve to a real
    # transcript turn is dropped, so an ungrounded guess never reaches the chart.
    valid_item_ids = {item.item_id for item in transcript.items if item.item_id}
    kept = []
    for item in result.items:
        if item.status in ("answered", "denied") and not any(turn.item_id in valid_item_ids for turn in item.evidence):
            log.info(f"questionnaire fill: dropping ungrounded item {item.question_dbid}")
            continue
        kept.append(item)
    gated: QuestionnaireFillResult = result.model_copy(update={"items": kept})
    return gated


# Failure kinds recorded per run. Keyed off the status code so a timeout is never again
# reported as "LLM returned 400", which pointed at a malformed request when the real cause
# was a chunk pushing past the SDK's fixed 30s ceiling.
FAILURE_KINDS = {
    HTTPStatus.REQUEST_TIMEOUT: "timeout",
    HTTPStatus.TOO_MANY_REQUESTS: "rate_limited",
    HTTPStatus.SERVICE_UNAVAILABLE: "connection_error",
    HTTPStatus.BAD_REQUEST: "bad_request",
}


# Failure kinds that mean the API is unavailable, so the remaining chunks should be
# abandoned rather than each marching into its own 30-second timeout. Everything else -
# a parse error above all - means the API answered and the fan-out is still worth running.
# A single stray key in one response used to abandon every chunk of every questionnaire on
# the note, so one bad answer to one questionnaire took the other two down with it.
ABORT_KINDS = frozenset({"timeout", "connection_error", "rate_limited", "server_error", "raised"})


def failure_kind(code: Any) -> str:
    """Human-readable cause for a non-OK status."""
    if code in FAILURE_KINDS:
        return FAILURE_KINDS[code]
    try:
        return "server_error" if int(code) >= 500 else "client_error"
    except (TypeError, ValueError):
        return "unknown"


def _salvage_items(payload: Any) -> QuestionnaireFillResult | None:
    """Keep the items that validate when the response as a whole does not.

    A chunk is one request carrying the whole transcript, so throwing away every answer
    because one of them is malformed is the most expensive possible reaction to the
    smallest possible defect. Returns None when there is nothing to salvage, which sends
    the caller back to raising ``parse_error``.
    """
    if not isinstance(payload, dict):
        return None
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return None
    kept = []
    for raw in raw_items:
        try:
            kept.append(QuestionnaireItemFill.model_validate(raw))
        except Exception:
            log.info("questionnaire fill: dropping an item that did not validate")
    if not kept:
        return None
    return QuestionnaireFillResult(items=kept)


class FillChunkError(Exception):
    """A chunk failed. ``retryable`` distinguishes an overloaded API from a bad request."""

    def __init__(self, message: str, retryable: bool = False, kind: str = "unknown") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.kind = kind


def fill_chunk(
    name: str,
    questions: list[dict[str, Any]],
    transcript: Transcript,
    client: ScribeLlmAnthropic,
) -> QuestionnaireFillResult:
    """Ask the model to answer one chunk of questions. Raises ``FillChunkError`` on failure."""
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])
    # Two separate calls, not one joined string: they become two content blocks, which is
    # what lets the transcript be cached while the chunk definition varies per request.
    client.set_user_prompt(["TRANSCRIPT (one object per turn):", "```json", _render_transcript(transcript), "```"])
    client.set_user_prompt(
        [f"QUESTIONNAIRE DEFINITION '{name}':", "```json", _render_definition(name, questions), "```"]
    )
    client.set_schema(QuestionnaireFillResult)
    try:
        response = client.request()
    except Exception as exc:
        raise FillChunkError(f"LLM request raised: {exc}", retryable=True, kind="raised") from exc
    if response.code != HTTPStatus.OK:
        # 408 is a timeout and stays non-retryable: the 30s ceiling is fixed, so a second
        # attempt burns another 30 seconds on the same too-large chunk. 503 is a transient
        # connection error and IS retried, which it was not while it shared the 400 bucket
        # with timeouts.
        kind = failure_kind(response.code)
        retryable = response.code in _RETRYABLE or int(response.code) >= 500
        raise FillChunkError(f"{kind} (HTTP {int(response.code)}): {response.response}", retryable=retryable, kind=kind)
    if getattr(client, "last_stop_reason", "") == "max_tokens":
        # Loud rather than silent. The response is well-formed and empty, so without this
        # the chunk reports a clean abstention on every question it was asked.
        raise FillChunkError(
            f"{FAILURE_TRUNCATED}: response cut off at max_tokens, answers discarded",
            retryable=False,
            kind=FAILURE_TRUNCATED,
        )
    try:
        payload = json.loads(response.response)
    except (ValueError, TypeError) as exc:
        raise FillChunkError(f"parse_error: {response.response}", kind="parse_error") from exc
    try:
        result = QuestionnaireFillResult.model_validate(payload)
    except Exception as exc:
        salvaged = _salvage_items(payload)
        if salvaged is None:
            raise FillChunkError(f"parse_error: {response.response}", kind="parse_error") from exc
        log.info(f"questionnaire fill: salvaged {len(salvaged.items)} item(s) from a response that did not validate")
        result = salvaged
    return _apply_grounding_gate(result, transcript)


def fill_chunk_with_retry(
    name: str,
    questions: list[dict[str, Any]],
    transcript: Transcript,
    client: ScribeLlmAnthropic,
    sleep: Callable[[float], None] = time.sleep,
) -> QuestionnaireFillResult:
    """One narrow retry, for an overloaded or briefly broken API only."""
    try:
        return fill_chunk(name, questions, transcript, client)
    except FillChunkError as exc:
        if not exc.retryable:
            raise
        log.info(f"questionnaire fill: retrying chunk of '{name}' [{exc.kind}] after {exc}")
        # random.uniform, not random.random(): the sandbox allowlists module attributes
        # by name and random is not among them.
        sleep(random.uniform(0.4, 1.0))
        return fill_chunk(name, questions, transcript, client)


def build_fill_command_data(
    definition: dict[str, Any],
    items_by_dbid: dict[int, QuestionnaireItemFill],
) -> dict[str, Any]:
    """Build the command payload the questionnaire card renders and the parser consumes.

    Every question is emitted, answered or not, in the shape ``handleSelectTemplate``
    builds in ``summary.js``. Emitting only the answered subset — as an earlier version did
    — leaves the provider unable to finish the form by hand and breaks scoring, because
    ``computeScore`` needs ``score_value`` on every response and ``isComplete`` needs every
    question present.

    Each question also carries a ``fill`` block with the status, confidence, rationale and
    evidence. The card reads it for provenance; ``QuestionnaireParser.build`` ignores it.
    """

    def response_for(option: dict[str, Any], selected: bool, value: Any = None) -> dict[str, Any]:
        return {
            "dbid": option["dbid"],
            "value": option["value"] if value is None else value,
            "code": option.get("code", ""),
            "score_value": option.get("score_value", ""),
            "selected": selected,
            "comment": None,
        }

    out_questions: list[dict[str, Any]] = []
    for question in definition["questions"]:
        question_type = question["type"]
        options: list[dict[str, Any]] = question["options"]
        candidate = items_by_dbid.get(question["dbid"])
        # ``not_assessed`` means the transcript never addressed the question, which is a
        # deliberate abstention rather than an answer, so it is treated as undrafted.
        item = candidate if candidate is not None and candidate.status in ("answered", "denied") else None

        if question_type in (ResponseOption.TYPE_TEXT, ResponseOption.TYPE_INTEGER):
            text = str(item.value) if item is not None and item.value is not None else ""
            if not text.strip():
                text, item = "", None
            if options:
                responses = [response_for(options[0], selected=bool(text), value=text)]
            else:
                responses = [
                    {
                        "dbid": None,
                        "value": text,
                        "code": "",
                        "score_value": "",
                        "selected": bool(text),
                        "comment": None,
                    }
                ]
        elif question_type == ResponseOption.TYPE_RADIO:
            chosen = item.selected_option_dbid if item is not None else None
            responses = [response_for(o, selected=o["dbid"] == chosen) for o in options]
            if not any(r["selected"] for r in responses):
                item = None
        else:  # TYPE_CHECKBOX
            affirmed = set(item.selected_option_dbids or []) if item is not None else set()
            responses = [response_for(o, selected=o["dbid"] in affirmed) for o in options]
            if not affirmed:
                item = None

        entry: dict[str, Any] = {
            "dbid": question["dbid"],
            "label": question["label"],
            "type": question_type,
            "responses": responses,
        }
        if item is not None:
            entry["fill"] = {
                "status": item.status,
                "confidence": item.confidence,
                "rationale": item.rationale,
                "evidence": [
                    {"speaker": turn.speaker, "quote": turn.quote, "item_id": turn.item_id} for turn in item.evidence
                ],
            }
        out_questions.append(entry)

    return {
        "questionnaire_dbid": definition["questionnaire_dbid"],
        "questionnaire_name": definition["questionnaire_name"],
        "is_scored": definition["is_scored"],
        "scoring_function_name": definition["scoring_function_name"],
        "questions": out_questions,
    }


# Outcome of one questionnaire's fill. Stated explicitly rather than inferred, because
# a drafted count plus a nullable error cannot distinguish the two cases that matter
# most: "read the transcript and nothing supported an answer" is the grounding rule
# working, and "never ran" is a bug. Both used to look like drafted == 0, error == None.
STATUS_FILLED = "filled"
# Some answers landed and some questions were never assessed, because the chunk carrying them
# failed. Distinct from ``filled`` because the blank questions in this case were NOT
# considered and declined - they were never read. Those look identical on the card, and
# conflating them told the provider that silence was a finding.
STATUS_PARTIAL = "partial"
STATUS_ABSTAINED = "abstained"
STATUS_NO_TRANSCRIPT = "no_transcript"
STATUS_FAILED = "failed"


class FillOutcome:
    """Per-questionnaire result: what happened, and the command payload if there is one."""

    def __init__(
        self,
        questionnaire_dbid: int,
        status: str,
        data: dict[str, Any] | None = None,
        drafted: int = 0,
        total: int = 0,
        error: str | None = None,
        items: list[QuestionnaireItemFill] | None = None,
        unread: list[int] | None = None,
    ) -> None:
        self.questionnaire_dbid = questionnaire_dbid
        self.status = status
        self.data = data
        self.drafted = drafted
        self.total = total
        self.error = error
        self.items = items or []
        # dbids of questions whose chunk failed, so the model never saw them. Reported so
        # the card can say "3 could not be read" instead of leaving them looking abstained.
        self.unread = unread or []

    @property
    def assessed(self) -> int:
        """How many questions the model returned an opinion on, in any status.

        Separates a healthy abstention (it considered each question and declined, so this
        equals ``total``) from the model returning nothing at all (zero), which points at a
        schema or parse problem wearing abstention's clothes.
        """
        return len(self.items)


def fill_questionnaires(
    questionnaire_dbids: list[int],
    transcript: Transcript,
    api_key: str,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    client_factory: Callable[[], ScribeLlmAnthropic] | None = None,
) -> tuple[list[FillOutcome], dict[str, Any]]:
    """Fill every requested questionnaire, returning outcomes and run telemetry.

    Work is flattened across questionnaires into one list of chunks. The first chunk runs
    alone so it writes the prompt cache; the rest fan out behind it and read from it.
    Running them all at once would mean every request missing a cache no request had
    written yet, paying the 1.25x write premium N times over.

    The lone first chunk doubles as an outage probe. If it fails in a way that says the API
    is unavailable, the remaining chunks are abandoned rather than each marching into its
    own 30-second timeout.
    """
    telemetry: dict[str, Any] = {
        "model": model,
        "effort": effort,
        "chunks": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "aborted": False,
        "failures": {},
    }
    if not questionnaire_dbids:
        # Caller error, not an outcome.
        return [], telemetry
    if not transcript.items:
        # An outcome in its own right. Returning [] here made the frontend report
        # "Fill failed", which is wrong: nothing failed, there was nothing to read.
        return [FillOutcome(dbid, status=STATUS_NO_TRANSCRIPT) for dbid in questionnaire_dbids], telemetry

    def make_client() -> ScribeLlmAnthropic:
        if client_factory is not None:
            return client_factory()
        return make_fill_client(api_key, model=model, effort=effort, cache_index=TRANSCRIPT_BLOCK_INDEX)

    transcript_chars = sum(len(item.text) for item in transcript.items)
    telemetry["transcript_chars"] = transcript_chars

    definitions: dict[int, dict[str, Any]] = {}
    errors: dict[int, str] = {}
    # Question dbids belonging to chunks that failed, per questionnaire.
    unread: dict[int, set[int]] = {}
    results: dict[int, dict[int, QuestionnaireItemFill]] = {}
    work: list[tuple[int, list[dict[str, Any]]]] = []
    for dbid in questionnaire_dbids:
        try:
            definition = load_questionnaire(dbid)
        except Exception:
            log.exception(f"questionnaire fill: could not load questionnaire {dbid}")
            errors[dbid] = "load_failed"
            continue
        definitions[dbid] = definition
        results[dbid] = {}
        unread[dbid] = set()
        for chunk in chunk_questions(definition["questions"], transcript_chars):
            work.append((dbid, chunk))

    telemetry["chunks"] = len(work)

    # Explicit reassignment, not ``+=``: the plugin sandbox rejects augmented assignment
    # on a subscript.
    usage_keys = (
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
        ("cache_read_tokens", "cache_read_input_tokens"),
        ("cache_write_tokens", "cache_creation_input_tokens"),
    )

    def record(usage: dict[str, Any]) -> None:
        for local_key, usage_key in usage_keys:
            telemetry[local_key] = telemetry[local_key] + (usage.get(usage_key) or 0)

    def run(
        unit: tuple[int, list[dict[str, Any]]],
    ) -> tuple[int, QuestionnaireFillResult | None, str | None, str | None]:
        dbid, chunk = unit
        client = make_client()
        try:
            result = fill_chunk_with_retry(definitions[dbid]["questionnaire_name"], chunk, transcript, client)
        except FillChunkError as exc:
            failures = telemetry["failures"]
            failures[exc.kind] = failures.get(exc.kind, 0) + 1
            log.info(f"questionnaire fill: chunk failed for {dbid} [{exc.kind}]: {exc}")
            record(client.last_usage)
            # ``.update()`` rather than ``|=``: the sandbox rejects augmented assignment on
            # a subscript.
            unread[dbid].update(question["dbid"] for question in chunk)
            return dbid, None, str(exc), exc.kind
        record(client.last_usage)
        return dbid, result, None, None

    if work:
        # Warm-up: one chunk alone, writing the cache the rest will read.
        first_dbid, first_result, first_error, first_kind = run(work[0])
        if first_error is not None and first_kind in ABORT_KINDS and len(work) > 1:
            # The probe says the API itself is unavailable. Everything else shares the
            # same API and the same transcript, so marching each remaining chunk into its
            # own timeout would only rediscover this.
            log.info(
                f"questionnaire fill: warm-up chunk failed, abandoning the fan-out "
                f"({len(work) - 1} chunk(s) skipped): {first_error}"
            )
            telemetry["aborted"] = True
            for dbid in definitions:
                errors.setdefault(dbid, first_error)
            # Nothing after the probe ran, so every question in every skipped chunk is unread.
            for skipped_dbid, skipped_chunk in work[1:]:
                unread[skipped_dbid].update(question["dbid"] for question in skipped_chunk)
            work = []
        else:
            if first_result is not None:
                for item in first_result.items:
                    results[first_dbid][item.question_dbid] = item
            elif first_error is not None:
                errors.setdefault(first_dbid, first_error)
            work = work[1:]

    if work:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            for dbid, result, error, _kind in pool.map(run, work):
                if result is not None:
                    for item in result.items:
                        results[dbid][item.question_dbid] = item
                elif error is not None:
                    # One chunk failing costs only its own questions; they stay blank and
                    # editable rather than taking the whole questionnaire down.
                    errors.setdefault(dbid, error)

    outcomes: list[FillOutcome] = []
    for dbid in questionnaire_dbids:
        if dbid not in definitions:
            outcomes.append(FillOutcome(dbid, status=STATUS_FAILED, error=errors.get(dbid, "load_failed")))
            continue
        items_by_dbid = results.get(dbid, {})
        data = build_fill_command_data(definitions[dbid], items_by_dbid)
        drafted = sum(1 for question in data["questions"] if "fill" in question)
        # A chunk error does not make the whole questionnaire a failure when answers landed -
        # the surviving ones are real. But it is not a clean fill either: the questions in the
        # failed chunk were never read, and reporting that as ``filled`` left them looking
        # like the model had considered them and declined. The error is kept in every case
        # where one occurred, so the cause survives into the audit row.
        error = errors.get(dbid)
        never_read = sorted(unread.get(dbid, set()))
        if drafted and never_read:
            status = STATUS_PARTIAL
        elif drafted:
            status = STATUS_FILLED
        elif error:
            status = STATUS_FAILED
        else:
            status = STATUS_ABSTAINED
        outcomes.append(
            FillOutcome(
                dbid,
                status=status,
                data=data,
                drafted=drafted,
                total=len(data["questions"]),
                error=error,
                items=list(items_by_dbid.values()),
                unread=never_read,
            )
        )
    return outcomes, telemetry
