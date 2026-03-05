from __future__ import annotations

from http import HTTPStatus
from typing import Union

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import JSONResponse, Response
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPI, api

from hyperscribe.scribe.backend import ScribeBackend, ScribeError, get_backend_from_secrets

_backend: ScribeBackend | None = None


def _get_or_create_backend(secrets: dict[str, str]) -> ScribeBackend:
    global _backend  # noqa: PLW0603
    if _backend is None:
        _backend = get_backend_from_secrets(secrets)
    return _backend


def _clear_backend() -> None:
    global _backend  # noqa: PLW0603
    _backend = None


class ScribeSessionView(SimpleAPI):
    """Scribe session management API."""

    PREFIX = "/scribe-session"

    def authenticate(self, credentials: Credentials) -> bool:
        return True

    @api.post("/start")
    def start(self) -> list[Union[Response, Effect]]:
        try:
            backend = _get_or_create_backend(self.secrets)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            backend.start_session()
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse({"status": "started"}, status_code=HTTPStatus.OK)]

    @api.post("/audio")
    def audio(self) -> list[Union[Response, Effect]]:
        if _backend is None:
            return [JSONResponse({"error": "No active session"}, status_code=HTTPStatus.CONFLICT)]
        form_data = self.request.form_data()
        audio_part = form_data.get("audio")
        if audio_part is None:
            return [JSONResponse({"error": "Missing 'audio' form part"}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            _backend.send_audio(audio_part.content)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse({"status": "ok"}, status_code=HTTPStatus.ACCEPTED)]

    @api.get("/transcript")
    def transcript(self) -> list[Union[Response, Effect]]:
        if _backend is None:
            return [JSONResponse({"error": "No active session"}, status_code=HTTPStatus.CONFLICT)]
        try:
            items = _backend.get_transcript_updates()
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [
            JSONResponse(
                {
                    "items": [
                        {
                            "text": item.text,
                            "speaker": item.speaker,
                            "start_offset_ms": item.start_offset_ms,
                            "end_offset_ms": item.end_offset_ms,
                            "item_id": item.item_id,
                            "is_final": item.is_final,
                        }
                        for item in items
                    ],
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/end")
    def end(self) -> list[Union[Response, Effect]]:
        if _backend is None:
            return [JSONResponse({"error": "No active session"}, status_code=HTTPStatus.CONFLICT)]
        try:
            transcript = _backend.end_session()
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        finally:
            _clear_backend()
        return [
            JSONResponse(
                {
                    "status": "ended",
                    "transcript": {
                        "items": [
                            {
                                "text": item.text,
                                "speaker": item.speaker,
                                "start_offset_ms": item.start_offset_ms,
                                "end_offset_ms": item.end_offset_ms,
                                "item_id": item.item_id,
                                "is_final": item.is_final,
                            }
                            for item in transcript.items
                        ],
                    },
                },
                status_code=HTTPStatus.OK,
            )
        ]
