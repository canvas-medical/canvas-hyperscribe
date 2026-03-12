from http import HTTPStatus
from typing import Union

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, Response
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin, api
from canvas_sdk.templates import render_to_string
from canvas_sdk.v1.data.note import Note
from canvas_sdk.v1.data.staff import Staff

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
        provider = Staff.objects.get(id=staff_id)
        provider_name = provider.credentialed_name

        note = Note.objects.select_related("patient").get(id=note_id)
        patient_name = note.patient.full_name

        html = render_to_string(
            "scribe/static/index.html",
            {
                "note_id": note_id,
                "view": view,
                "provider_name": provider_name,
                "provider_photo_url": provider.photo_url,
                "patient_name": patient_name,
                "patient_id": str(note.patient.id),
                "staff_id": str(staff_id),
                "staff_name": provider_name,
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
