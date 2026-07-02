"""Tests for the grounded-LLM diagnosis resolver.

The resolver is an oracle over a RETRIEVED set of real ICD-10 codes: it may only
select codes present in the pool (belt suggestions + science-search hits), and it
expands the search when nothing provided fits. These tests assert the anti-
hallucination gate, the auto-apply-only-on-high-confidence policy, the adaptive
expansion round, and best-effort failure handling — all with a fake LLM client and
an injected fake science search (no network).
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from hyperscribe.scribe.recommendations.diagnosis_llm_resolver import (
    BlockContext,
    resolve_uncoded_blocks,
)
from hyperscribe.structures.icd10_condition import Icd10Condition


class _Resp:
    def __init__(self, response: str, code: HTTPStatus = HTTPStatus.OK) -> None:
        self.code = code
        self.response = response


class _FakeClient:
    """Returns queued structured responses in order; optionally raises on request()."""

    def __init__(self, responses: list[_Resp], raise_on_request: bool = False) -> None:
        self._responses = list(responses)
        self._raise = raise_on_request

    def reset_prompts(self) -> None: ...
    def set_system_prompt(self, _prompt: Any) -> None: ...
    def set_user_prompt(self, _prompt: Any) -> None: ...
    def set_schema(self, _schema: Any) -> None: ...

    def request(self) -> _Resp:
        if self._raise:
            raise RuntimeError("boom")
        assert self._responses, "no more queued responses"
        return self._responses.pop(0)


def _step(
    selected: str | None = None,
    confidence: str = "low",
    ranked: list[str] | None = None,
    terms: list[str] | None = None,
    code: HTTPStatus = HTTPStatus.OK,
) -> _Resp:
    # BaseModelLlmJson camelCases field aliases (extra="forbid"), so the LLM's JSON —
    # and therefore these fixtures — must use camelCase keys.
    return _Resp(
        json.dumps(
            {
                "selectedCode": selected,
                "confidence": confidence,
                "rankedCodes": ranked or [],
                "moreSearchTerms": terms or [],
            }
        ),
        code=code,
    )


def _candidate(code: str, formatted: str, display: str, provenance: str = "Detected in note") -> dict[str, str]:
    return {"code": code, "formatted_code": formatted, "display": display, "provenance": provenance}


def _factory(client: _FakeClient) -> Any:
    return lambda: client


def _no_science(_terms: list[str]) -> list[Icd10Condition]:
    return []


def test_selects_from_provided_high_confidence_auto_applies() -> None:
    block = BlockContext(
        block_id="apblock-1",
        header="Edema in lower extremities",
        body="Edema in legs may be exacerbated by high sodium intake.",
        candidates=[_candidate("R60.0", "R60.0", "Localized edema")],
    )
    client = _FakeClient([_step(selected="R60.0", confidence="high", ranked=["R60.0"])])
    out = resolve_uncoded_blocks([block], _factory(client), _no_science)

    assert out["apblock-1"].chosen == ("R60.0", "Localized edema")
    assert out["apblock-1"].confidence == "high"


def test_expands_when_nothing_provided_then_selects() -> None:
    # "Fluid overload" — belt found nothing; the LLM asks for a search, science grounds
    # E87.70, and the LLM selects it. Demonstrates the no-code-when-one-exists fix.
    block = BlockContext(
        block_id="apblock-0",
        header="Fluid overload and pulmonary symptoms",
        body="Fluid overload with pulmonary symptoms, managed with oxygen therapy.",
        candidates=[],
    )
    science_calls: list[list[str]] = []

    def science(terms: list[str]) -> list[Icd10Condition]:
        science_calls.append(terms)
        return [Icd10Condition(code="E8770", label="Fluid overload, unspecified")]

    client = _FakeClient(
        [
            _step(terms=["fluid overload", "pulmonary edema"]),  # round 1: expand
            _step(selected="E87.70", confidence="high", ranked=["E87.70"]),  # round 2: select
        ]
    )
    out = resolve_uncoded_blocks([block], _factory(client), science)

    assert science_calls == [["fluid overload", "pulmonary edema"]]
    assert out["apblock-0"].chosen == ("E87.70", "Fluid overload, unspecified")


def test_rejects_clinically_wrong_provided_and_expands() -> None:
    # "Protein intake" seeded with the inverted lexical hit E67.8 (hyperalimentation).
    # The LLM must NOT select it; it expands to hypoalbuminemia and picks E88.09.
    block = BlockContext(
        block_id="apblock-2",
        header="Protein intake",
        body="Albumin is slightly low, indicating need for increased dietary protein.",
        candidates=[_candidate("E678", "E67.8", "Other specified hyperalimentation", "ICD-10 search")],
    )

    def science(_terms: list[str]) -> list[Icd10Condition]:
        return [Icd10Condition(code="E8809", label="Hypoalbuminemia")]

    client = _FakeClient(
        [
            _step(terms=["hypoalbuminemia"]),  # rejects E67.8, expands
            _step(selected="E88.09", confidence="high", ranked=["E88.09"]),
        ]
    )
    out = resolve_uncoded_blocks([block], _factory(client), science)

    assert out["apblock-2"].chosen == ("E88.09", "Hypoalbuminemia")
    # The inverted code was never chosen.
    assert out["apblock-2"].chosen != ("E67.8", "Other specified hyperalimentation")


def test_wrong_family_refinement_expands_to_correct_family() -> None:
    # "Anemia" seeded with D64.9 (unspecified). The LLM expands to iron-deficiency and
    # picks D50.9 — the note-indicated family — instead of the D64 siblings.
    block = BlockContext(
        block_id="apblock-3",
        header="Anemia",
        body="Mild anemia present. Iron deficiency to be considered.",
        candidates=[_candidate("D64.9", "D64.9", "Anemia, unspecified")],
    )

    def science(_terms: list[str]) -> list[Icd10Condition]:
        return [Icd10Condition(code="D509", label="Iron deficiency anemia, unspecified")]

    client = _FakeClient(
        [
            _step(terms=["iron deficiency anemia"]),
            _step(selected="D50.9", confidence="high", ranked=["D50.9", "D64.9"]),
        ]
    )
    out = resolve_uncoded_blocks([block], _factory(client), science)

    assert out["apblock-3"].chosen == ("D50.9", "Iron deficiency anemia, unspecified")


def test_hallucinated_code_is_rejected() -> None:
    # The LLM returns a code that is NOT in the pool and offers no search terms.
    # Nothing survives the gate -> no resolution (belt output preserved).
    block = BlockContext(
        block_id="apblock-9",
        header="Some problem",
        body="",
        candidates=[_candidate("R60.0", "R60.0", "Localized edema")],
    )
    client = _FakeClient([_step(selected="Z99.9", confidence="high", ranked=["Z99.9"])])
    out = resolve_uncoded_blocks([block], _factory(client), _no_science)

    assert "apblock-9" not in out


def test_medium_confidence_surfaces_not_auto_applied() -> None:
    block = BlockContext(
        block_id="apblock-4",
        header="Anemia",
        body="Mild anemia.",
        candidates=[
            _candidate("D64.9", "D64.9", "Anemia, unspecified"),
            _candidate("D501", "D50.1", "Sideropenic dysphagia"),
        ],
    )
    client = _FakeClient([_step(selected="D64.9", confidence="medium", ranked=["D64.9", "D50.1"])])
    out = resolve_uncoded_blocks([block], _factory(client), _no_science)

    res = out["apblock-4"]
    assert res.chosen is None  # medium never auto-applies
    assert [s["formatted_code"] for s in res.suggestions] == ["D64.9", "D50.1"]


def test_suggestions_drop_out_of_pool_ranked_codes() -> None:
    # A ranked code not in the pool is filtered out; the in-pool one survives.
    block = BlockContext(
        block_id="apblock-5",
        header="Anemia",
        body="",
        candidates=[_candidate("D64.9", "D64.9", "Anemia, unspecified")],
    )
    client = _FakeClient([_step(selected="D64.9", confidence="medium", ranked=["D64.9", "FAKE99"])])
    out = resolve_uncoded_blocks([block], _factory(client), _no_science)

    codes = [s["formatted_code"] for s in out["apblock-5"].suggestions]
    assert codes == ["D64.9"]


def test_best_effort_on_client_error_yields_no_resolution() -> None:
    block = BlockContext(block_id="apblock-6", header="X", body="", candidates=[])
    client = _FakeClient([], raise_on_request=True)
    out = resolve_uncoded_blocks([block], _factory(client), _no_science)

    assert out == {}


def test_no_selection_no_terms_gives_up() -> None:
    block = BlockContext(
        block_id="apblock-7",
        header="Physical therapy access",
        body="Difficulty accessing home health PT.",
        candidates=[],
    )
    client = _FakeClient([_step(selected=None, confidence="low")])
    out = resolve_uncoded_blocks([block], _factory(client), _no_science)

    assert "apblock-7" not in out
