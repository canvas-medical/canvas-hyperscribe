from datetime import datetime, UTC
from http import HTTPStatus

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, JSONResponse, Broadcast
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from requests import post as requests_post

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings


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
        messages = []
        if (key := self.key_cache()) and (cached := get_cache().get(key)):
            messages = cached
        return [JSONResponse({"time": now.isoformat(), "messages": messages})]

    def post(self) -> list[Response | Effect]:
        if key := self.key_cache():
            cached = get_cache().get(key)
            if not isinstance(cached, list):
                cached = []
            cached.append(self.request.json())
            get_cache().set(key, cached)

        return [
            Broadcast(message=self.request.json(), channel=Constants.WS_CHANNEL_PROGRESSES).apply(),
            JSONResponse({"status": "ok"}, status_code=HTTPStatus.ACCEPTED),
        ]

    def key_cache(self) -> str:
        if note_id := self.request.query_params.get("note_id"):
            return f"progress-{note_id}"
        return ""

    @classmethod
    def send_to_user(
        cls,
        identification: IdentificationParameters,
        settings: Settings,
        message: str,
        section: str,
    ) -> None:
        if settings.send_progress:
            requests_post(
                Authenticator.presigned_url(
                    settings.api_signing_key,
                    f"{Helper.canvas_host(identification.canvas_instance)}{Constants.PLUGIN_API_BASE_ROUTE}/progress",
                    {"note_id": identification.note_uuid},
                ),
                headers={"Content-Type": "application/json"},
                json={"time": datetime.now(UTC).isoformat(), "message": message, "section": section},
                verify=True,
                timeout=None,
            )
