import json
from hashlib import sha256
from http import HTTPStatus
from time import time

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, Response
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from canvas_sdk.templates import render_to_string

from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials


class ReviewerDisplay(SimpleAPIRoute):
    PATH = "/reviewer"

    def authenticate(self, credentials: Credentials) -> bool:
        params = self.request.query_params

        if not ("ts" in params and "sig" in params):
            return False

        timestamp = int(params["ts"])
        if (time() - timestamp) > Constants.AWS3_LINK_EXPIRATION_SECONDS:
            return False

        hash_arg = f"{timestamp}{self.secrets[Constants.SECRET_AWS_SECRET]}"
        internal_sig = sha256(hash_arg.encode('utf-8')).hexdigest()
        request_sig = params["sig"]

        return bool(request_sig == internal_sig)

    def get(self) -> list[Response | Effect]:
        url_list: list[str] = []

        credentials = AwsS3Credentials.from_dictionary(self.secrets)
        client_s3 = AwsS3(credentials)
        if client_s3.is_ready() and (note_uuid := self.request.query_params.get("note_id")):
            canvas_instance = self.environment[Constants.CUSTOMER_IDENTIFIER]
            store_path = (f"{canvas_instance}/"
                          "audits/"
                          f"{note_uuid}/")
            url_list = [
                client_s3.generate_presigned_url(
                    document.key,
                    Constants.AWS3_LINK_EXPIRATION_SECONDS,
                )
                for document in client_s3.list_s3_objects(store_path)
            ]

        context = {
            "url_list": json.dumps(url_list),
        }
        return [
            HTMLResponse(
                render_to_string('templates/reviewer.html', context),
                status_code=HTTPStatus.OK,
            )
        ]
