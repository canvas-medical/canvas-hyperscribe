from typing import Any

from django.db.models import DO_NOTHING, BooleanField, DateTimeField, JSONField, Model, OneToOneField, TextField

try:
    from canvas_sdk.v1.data.base import CustomModel
except ImportError:
    CustomModel = Model

from hyperscribe.models.proxy import NoteProxy, _HAS_MODEL_EXTENSION


class _FallbackMeta:
    """Provides app_label when running locally without CustomModel."""

    if not _HAS_MODEL_EXTENSION:
        app_label = "v1"
        managed = False


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
    updated_at: Any = DateTimeField(auto_now=True)

    class Meta(_FallbackMeta):
        pass


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
    selected_template_name: Any = TextField(default="")
    mode: Any = TextField(default="")
    raw_response: Any = JSONField(default=dict)
    updated_at: Any = DateTimeField(auto_now=True)

    class Meta(_FallbackMeta):
        pass


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

    class Meta(_FallbackMeta):
        pass
