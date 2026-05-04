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
        # Only the three fields we actually use downstream (id, patient_id,
        # provider_id). Avoids materializing the full Note row for what is
        # effectively a primary-key lookup feeding two scalar FK comparisons.
        note = Note.objects.only("id", "patient_id", "provider_id").get(id=note_id)
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
    log.info(
        "prior_sections: lookup patient=%s provider=%s excluding note=%s states=%s",
        note.patient_id, note.provider_id, note_id, _FINALIZED_STATES,
    )

    try:
        base = (
            Command.objects.filter(
                note__patient_id=note.patient_id,
                note__provider_id=note.provider_id,
                note__current_state__state__in=_FINALIZED_STATES,
                note__datetime_of_service__lte=now,
                schema_key__in=(_PE_KEY, _ROS_KEY),
            )
            .exclude(note_id=note.id)
            .select_related("note")
        )
        # Diagnostic count — separate from .first() so we can see how many
        # candidate commands existed before we picked the most-recent one.
        candidate_count = base.count()
        pe_cmd = base.filter(schema_key=_PE_KEY).order_by("-note__datetime_of_service").first()
        ros_cmd = base.filter(schema_key=_ROS_KEY).order_by("-note__datetime_of_service").first()
    except Exception:
        log.exception("prior_sections: query failed for note %s", note_id)
        return empty

    log.info(
        "prior_sections: candidates=%s pe_found=%s ros_found=%s",
        candidate_count,
        bool(pe_cmd),
        bool(ros_cmd),
    )

    try:
        result = {
            "physical_exam": _command_to_payload(pe_cmd),
            "review_of_systems": _command_to_payload(ros_cmd),
        }
    except Exception:
        log.exception("prior_sections: payload build failed for note %s", note_id)
        return empty

    log.info(
        "prior_sections: returning pe=%s ros=%s",
        "payload" if result["physical_exam"] else "None",
        "payload" if result["review_of_systems"] else "None",
    )
    return result


def _command_to_payload(cmd: Command | None) -> dict[str, Any] | None:
    if cmd is None:
        return None

    raw = cmd.data
    is_dict = isinstance(raw, dict)
    data: dict[str, Any] = raw if is_dict else {}

    # Diagnostic: where does the HTML actually live? Log the keys we see and
    # try a few likely fields. Older Hyperscribe versions used different
    # template markup; this also covers print_content as a fallback.
    keys = list(data.keys()) if is_dict else type(raw).__name__
    log.info(
        "prior_sections: cmd %s schema=%s data_type=%s keys=%s",
        cmd.id, cmd.schema_key, type(raw).__name__, keys,
    )

    candidates: list[str] = []
    if is_dict:
        for key in ("content", "print_content", "html", "body"):
            value = data.get(key)
            if isinstance(value, str) and value:
                decoded = _maybe_b64decode(value)
                candidates.append(decoded)
                log.info(
                    "prior_sections: cmd %s key=%s raw_len=%d decoded_len=%d sample=%r",
                    cmd.id, key, len(value), len(decoded), decoded[:200],
                )
    elif isinstance(raw, str):
        decoded = _maybe_b64decode(raw)
        candidates.append(decoded)
        log.info(
            "prior_sections: cmd %s data is raw string raw_len=%d decoded_len=%d sample=%r",
            cmd.id, len(raw), len(decoded), decoded[:200],
        )

    sections: list[dict[str, str]] = []
    for html in candidates:
        sections = parse_ros_pe_html(html)
        if sections:
            log.info("prior_sections: cmd %s parsed %d sections", cmd.id, len(sections))
            break

    if not sections:
        log.info("prior_sections: cmd %s no sections parseable from %d candidate field(s)", cmd.id, len(candidates))
        return None
    note = cmd.note
    return {
        "source_note_id": str(note.id),
        "source_date": note.datetime_of_service.isoformat() if note.datetime_of_service else None,
        "sections": sections,
    }
