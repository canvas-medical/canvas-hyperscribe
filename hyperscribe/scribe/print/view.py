from typing import Union

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, Response
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin, api
from canvas_sdk.templates import render_to_string
from canvas_sdk.v1.data.note import Note

from hyperscribe.models.scribe import ScribeSummary
from hyperscribe.scribe.print.header import build_note_header_context
from hyperscribe.scribe.print.scribe_data import build_scribe_body_items


class PrintScribeNoteView(StaffSessionAuthMixin, SimpleAPI):
    """Serves the print HTML for a note using ScribeSummary data."""

    PREFIX = "/scribe-print"

    @api.get("/note/<note_id>")
    def print_note(self) -> list[Union[Response, Effect]]:
        note_id = self.request.path_params.get("note_id")
        if not note_id:
            return [Response(status_code=400, content=b"Missing note_id")]

        try:
            note = Note.objects.get(dbid=note_id)
        except Note.DoesNotExist:
            return [Response(status_code=404, content=b"Note not found")]

        summary_row = (
            ScribeSummary.objects.filter(note_id=note_id)
            .values("note_data", "commands", "recommendations", "approved")
            .first()
        )
        if not summary_row:
            return [Response(status_code=404, content=b"No Scribe data for this note")]

        body_items = build_scribe_body_items(
            summary_row.get("note_data"),
            summary_row.get("commands"),
            summary_row.get("recommendations"),
        )

        context = build_note_header_context(note)
        context["commands"] = body_items

        rendered_html = render_to_string("scribe/print/templates/print_scribe_note.html", context)
        if not rendered_html:
            return [Response(status_code=500, content=b"Template render failed")]

        return [HTMLResponse(content=rendered_html)]
