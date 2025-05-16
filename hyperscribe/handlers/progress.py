from datetime import datetime, UTC, timedelta

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, JSONResponse
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from requests import post as requests_post

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings

PROGRESS: dict[str, list[dict]] = {}  # store the messages sent to the UI


class Progress(SimpleAPIRoute):
    PATH = "/progress"

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    def get(self) -> list[Response | Effect]:
        now = datetime.now(UTC)
        self.clear(now)
        return [
            JSONResponse({
                "time": now.isoformat(),
                "messages": PROGRESS.get(self.request.query_params.get("note_id")) or [],
            })
        ]

    def post(self) -> list[Response | Effect]:
        if note_uuid := self.request.query_params.get("note_id"):
            if note_uuid not in PROGRESS:
                PROGRESS[note_uuid] = []
            PROGRESS[note_uuid].insert(0, self.request.json())
        return [JSONResponse({"received": True})]

    @classmethod
    def clear(cls, now: datetime) -> None:
        then = now - timedelta(seconds=Constants.PROGRESS_EXPIRATION_SECONDS)
        old_note_ids = [
            note_id
            for note_id, messages in PROGRESS.items()
            if messages and messages[0]["time"] < then.isoformat()
        ]
        for note_id in old_note_ids:
            del PROGRESS[note_id]

    @classmethod
    def send_to_user(cls, identification: IdentificationParameters, settings: Settings, message: str) -> None:
        if settings.send_progress:
            requests_post(
                Authenticator.presigned_url(
                    settings.api_signing_key,
                    f"{identification.canvas_host()}/plugin-io/api/hyperscribe/progress",
                    {"note_id": identification.note_uuid},
                ),
                headers={"Content-Type": "application/json"},
                json={
                    "time": datetime.now(UTC).isoformat(),
                    "message": message,
                },
                verify=True,
                timeout=None,
            )
