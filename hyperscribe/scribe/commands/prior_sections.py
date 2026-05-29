"""Look up the most recent prior Physical Exam / Review of Systems for the
same provider + same patient, scoped to finalized notes only.

This powers the "show last visit" reference UI in the Scribe view: providers
can scan their own previous PE/ROS as context without any of the content
being copied into the new note.

Scoping rules:
- Same patient as the current note.
- Same provider as the current note (single-author principle — never show
  another provider's prior work as the reference).
- Note current state must be locked or signed (finalized clinical record).
  In-process drafts and deleted notes are excluded.
- `datetime_of_service` must be in the past (no future-dated notes).
- The current note itself is excluded.

Each command type (PE, ROS) is queried independently and returns its own
most-recent prior occurrence. They may come from different source notes —
the most recent PE might predate the most recent ROS or vice versa.
"""

from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timezone
from typing import Any

from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

from hyperscribe.scribe.commands._section_html import parse_ros_pe_html


def _maybe_b64decode(value: str) -> str:
    """Canvas stores the CustomCommand `content` field as base64-encoded HTML
    in the Command's data JSONField. Decode if the value parses as base64
    (and decodes to UTF-8 text); otherwise return as-is so callers fall back
    to treating the value as already-decoded HTML.
    """
    if not value:
        return ""
    try:
        decoded = b64decode(value, validate=True).decode("utf-8")
        return decoded
    except Exception:
        return value


# Note states that count as "finalized clinical record" for our purposes.
# LKD = Locked, SGN = Signed (see canvas_sdk.v1.data.note.NoteStates).
_FINALIZED_STATES = ("LKD", "SGN")
_PE_KEY = "physicalExam"
_ROS_KEY = "reviewOfSystems"


def get_prior_section_data(note_id: str) -> dict[str, Any]:
    """Return the prior PE/ROS reference payload for the Scribe UI.

    Best-effort, never raises: any failure (note lookup, ORM relation
    mismatch across SDK versions, malformed HTML, etc.) is logged and
    treated as "no prior data," so the Scribe UI always renders.
    Emits diagnostic INFO logs at every decision point so we can tell
    "no data on this patient" apart from "query/parser failure".

    Output shape:
      {
        "physical_exam": None | {"source_note_id": str, "source_date": iso-str, "sections": [{title, text}]},
        "review_of_systems": None | {...},
      }
    """
    empty: dict[str, Any] = {"physical_exam": None, "review_of_systems": None}
    if not note_id:
        log.info("prior_sections: no note_id supplied")
        return empty
    try:
        # Only the four fields we actually use downstream (id, dbid,
        # patient_id, provider_id). Avoids materializing the full Note row
        # for what is effectively a primary-key lookup feeding two scalar FK
        # comparisons. dbid is required by the .exclude clause below — it
        # filters on Command.note_id which targets Note's BigAutoField PK,
        # NOT the UUID id field. Passing note.id (a uuid.UUID) into that
        # filter would compile to a 128-bit integer parameter that overflows
        # the bigint column and silently fails the whole query.
        note = Note.objects.only("id", "dbid", "patient_id", "provider_id").get(id=note_id)
    except Exception:
        log.exception("prior_sections: failed to load current note %s", note_id)
        return empty
    if not note.patient_id or not note.provider_id:
        log.info(
            "prior_sections: note %s missing patient_id (%s) or provider_id (%s); skipping",
            note_id, note.patient_id, note.provider_id,
        )
        return empty

    now = datetime.now(timezone.utc)

    try:
        base = (
            Command.objects.filter(
                note__patient_id=note.patient_id,
                note__provider_id=note.provider_id,
                note__current_state__state__in=_FINALIZED_STATES,
                note__datetime_of_service__lte=now,
                schema_key__in=(_PE_KEY, _ROS_KEY),
            )
            # note_id targets Note's BigAutoField PK (dbid), NOT id (UUID).
            # Pass note.dbid here — note.id would compile to a 128-bit int
            # that overflows bigint and triggers the silent-empty failure
            # mode in the surrounding try/except.
            .exclude(note_id=note.dbid)
            # Exclude voided commands. After PR #276's amendment workflow
            # (`void_recreate_custom` for PE/ROS), the OLD row persists with
            # `state="entered_in_error"` on the same finalized note alongside
            # the NEW committed row — both carry `data.content`, so without
            # this filter the retracted clinical text could surface as the
            # 'previous documentation' reference. Matches the codebase
            # convention (commander.py, capture_view.py, tuning_archiver.py,
            # case_builder.py all use state="staged" / state="committed").
            .exclude(state="entered_in_error")
            .select_related("note")
        )
        # `-dbid` is the deterministic tiebreaker for the case where both
        # the voided and the recreated row share `note__datetime_of_service`
        # (always true on amend within a single signed note). Without it
        # PostgreSQL's tie resolution is undefined and the wrong row can win.
        # The exclude above already drops the voided row, but the tiebreaker
        # guards against any future scenario where two valid rows tie.
        pe_cmd = base.filter(schema_key=_PE_KEY).order_by("-note__datetime_of_service", "-dbid").first()
        ros_cmd = base.filter(schema_key=_ROS_KEY).order_by("-note__datetime_of_service", "-dbid").first()
    except Exception:
        log.exception("prior_sections: query failed for note %s", note_id)
        return empty

    try:
        return {
            "physical_exam": _command_to_payload(pe_cmd),
            "review_of_systems": _command_to_payload(ros_cmd),
        }
    except Exception:
        log.exception("prior_sections: payload build failed for note %s", note_id)
        return empty


def _command_to_payload(cmd: Command | None) -> dict[str, Any] | None:
    if cmd is None:
        return None

    raw = cmd.data
    is_dict = isinstance(raw, dict)
    data: dict[str, Any] = raw if is_dict else {}

    # Try the candidate HTML-bearing fields in order. `content` is the modern
    # CustomCommand layout; the others are fallbacks for older Hyperscribe
    # markup. Each value is base64-decoded if it parses as base64; otherwise
    # treated as already-decoded HTML.
    candidates: list[str] = []
    if is_dict:
        for key in ("content", "print_content", "html", "body"):
            value = data.get(key)
            if isinstance(value, str) and value:
                candidates.append(_maybe_b64decode(value))
    elif isinstance(raw, str):
        candidates.append(_maybe_b64decode(raw))

    sections: list[dict[str, str]] = []
    for html in candidates:
        sections = parse_ros_pe_html(html)
        if sections:
            break

    if not sections:
        return None
    note = cmd.note
    return {
        "source_note_id": str(note.id),
        "source_date": note.datetime_of_service.isoformat() if note.datetime_of_service else None,
        "sections": sections,
    }
