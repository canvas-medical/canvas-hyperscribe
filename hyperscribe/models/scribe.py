from typing import Any

from django.db.models import DO_NOTHING, BooleanField, CharField, DateTimeField, JSONField, OneToOneField, TextField

from canvas_sdk.v1.data.base import CustomModel

from hyperscribe.models.proxy import NoteProxy


class ScribeTranscript(CustomModel):
    """Stores the recording transcript for a note."""

    note: Any = OneToOneField(
        NoteProxy,
        to_field="dbid",
        on_delete=DO_NOTHING,
        related_name="%(app_label)s__transcript",
        primary_key=True,
    )
    items: Any = JSONField(default=list)
    finalized: Any = BooleanField(default=False)
    provider_id: Any = CharField(max_length=32, default="", blank=True)
    updated_at: Any = DateTimeField(auto_now=True)


class ScribeSummary(CustomModel):
    """Stores the generated summary, commands, and recommendations for a note."""

    note: Any = OneToOneField(
        NoteProxy,
        to_field="dbid",
        on_delete=DO_NOTHING,
        related_name="%(app_label)s__summary",
        primary_key=True,
    )
    note_data: Any = JSONField(default=dict)
    commands: Any = JSONField(default=list)
    recommendations: Any = JSONField(default=list)
    unmatched_conditions: Any = JSONField(default=list)
    diagnosis_suggestions: Any = JSONField(default=dict)
    approved: Any = BooleanField(default=False)
    was_finalized: Any = BooleanField(default=False)
    selected_template_name: Any = TextField(default="")
    mode: Any = TextField(default="")
    raw_response: Any = JSONField(default=dict)
    updated_at: Any = DateTimeField(auto_now=True)


class ScribeAuditLog(CustomModel):
    """Append-only audit event log for debugging."""

    note: Any = OneToOneField(
        NoteProxy,
        to_field="dbid",
        on_delete=DO_NOTHING,
        related_name="%(app_label)s__audit_log",
        primary_key=True,
    )
    events: Any = JSONField(default=list)
    updated_at: Any = DateTimeField(auto_now=True)
