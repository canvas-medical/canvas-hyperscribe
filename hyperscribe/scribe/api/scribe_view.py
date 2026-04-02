from http import HTTPStatus
from typing import Union

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, Response
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin, api
from canvas_sdk.templates import render_to_string
from canvas_sdk.v1.data.note import Note
from canvas_sdk.v1.data.staff import Staff

from hyperscribe.libraries.helper import Helper
from hyperscribe.models.scribe import ScribeTranscript

CONTENT_TYPES: dict[str, str] = {
    "js": "text/javascript",
    "css": "text/css",
}


class ScribeView(StaffSessionAuthMixin, SimpleAPI):
    """Serve the Scribe UI and static assets."""

    PREFIX = "/scribe"

    @api.get("/app")
    def get_app(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        view = self.request.query_params.get("view", "")
        if not note_id or not view:
            return [
                HTMLResponse(
                    "<html><body>Error: note_id and view are required</body></html>",
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]

        staff_id = self.request.headers.get("canvas-logged-in-user-id")
        logged_in_staff = Staff.objects.get(id=staff_id)

        note = Note.objects.select_related("patient", "provider").get(id=note_id)
        patient_name = note.patient.full_name
        note_editable = Helper.editable_note(note.dbid)

        # Use the provider stored with the transcript (the user who recorded it).
        # Fall back to the note author, then a generic label.
        transcript_provider_id = ScribeTranscript.objects.filter(note_id=note.dbid).values_list("provider_id", flat=True).first()
        if transcript_provider_id:
            provider = Staff.objects.get(id=transcript_provider_id)
            provider_name = provider.credentialed_name
            provider_photo_url = provider.photo_url or ""
        elif note.provider:
            provider_name = note.provider.credentialed_name
            provider_photo_url = note.provider.photo_url or ""
        else:
            provider_name = "Unknown Provider"
            provider_photo_url = ""

        html = render_to_string(
            "scribe/static/index.html",
            {
                "note_id": note_id,
                "view": view,
                "provider_name": provider_name,
                "provider_photo_url": provider_photo_url,
                "patient_name": patient_name,
                "patient_id": str(note.patient.id),
                "staff_id": str(staff_id),
                "staff_name": logged_in_staff.credentialed_name,
                "debug_mode": "true" if self.secrets.get("ScribeDebugStaffers") else "",
                "note_editable": "true" if note_editable else "",
                "alert_facility_enabled": "true" if self.secrets.get("AlertFacilityEnabled") else "",
            },
        )
        return [HTMLResponse(html)]

    @api.get("/static/<filename>")
    def get_static(self) -> list[Union[Response, Effect]]:
        filename = self.request.path_params["filename"]
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        content_type = CONTENT_TYPES.get(extension)
        if not content_type:
            return [Response(b"Not found", status_code=HTTPStatus.NOT_FOUND)]

        content = render_to_string(f"scribe/static/{filename}")
        return [
            Response(
                content.encode(),
                status_code=HTTPStatus.OK,
                content_type=content_type,
            )
        ]
