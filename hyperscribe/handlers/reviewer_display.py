import json
from http import HTTPStatus

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, Response
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from canvas_sdk.templates import render_to_string

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials


class ReviewerDisplay(SimpleAPIRoute):
    PATH = "/reviewer"

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    def get(self) -> list[Response | Effect]:
        url_list: list[str] = []

        credentials = AwsS3Credentials.from_dictionary(self.secrets)
        client_s3 = AwsS3(credentials)
        if client_s3.is_ready() and (note_uuid := self.request.query_params.get("note_id")):
            canvas_instance = self.environment[Constants.CUSTOMER_IDENTIFIER]
            store_path = f"hyperscribe-{canvas_instance}/audits/{note_uuid}/"
            url_list = [
                client_s3.generate_presigned_url(document.key, Constants.AWS3_LINK_EXPIRATION_SECONDS)
                for document in client_s3.list_s3_objects(store_path)
            ]

        context = {"url_list": json.dumps(url_list)}
        return [HTMLResponse(render_to_string("templates/reviewer.html", context), status_code=HTTPStatus.OK)]
