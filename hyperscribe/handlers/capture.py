from http import HTTPStatus

from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from canvas_sdk.effects.simple_api import HTMLResponse, Response
from canvas_sdk.effects import Effect
from canvas_sdk.templates import render_to_string

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.authenticator import Authenticator



class CaptureView(SimpleAPIRoute):
    PATH = "/capture/<patient_id>/<note_id>"

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    def get(self) -> list[Response | Effect]:
        self.request.path_params["id"]
        context = {'patientId': 'Johnny'}
        return [
            HTMLResponse(
                render_to_string('templates/hyperscribe.html', context),
                status_code=HTTPStatus.OK,
            )
        ]
