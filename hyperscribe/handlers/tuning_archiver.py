import json
from hashlib import sha256
from http import HTTPStatus
from time import time

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, JSONResponse, Response
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from canvas_sdk.handlers.simple_api.api import Request
from canvas_sdk.templates import render_to_string
from canvas_sdk.v1.data import Note

from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.limited_cache_loader import LimitedCacheLoader
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters


class TuningArchiver(SimpleAPIRoute):
    PATH = "/archive"

    def authenticate(self, credentials: Credentials) -> bool:
        query_params = self.request.query_params

        # Need signing params
        if "ts" not in query_params or "sig" not in query_params:
            return False

        timestamp = int(query_params["ts"])

        # No good if more than one hour old
        if (time() - timestamp) > Constants.MAX_AUTHENTICATION_TIME:
            return False

        request_sig = query_params["sig"]
        hash_arg = query_params["ts"] + self.secrets[Constants.SECRET_API_SIGNING_KEY]
        internal_sig = sha256(hash_arg.encode("utf-8")).hexdigest()

        return bool(request_sig == internal_sig)

    def get(self) -> list[Response | Effect]:
        qp = self.request.query_params

        # force the interval to 15s or more
        interval = self.secrets[Constants.SECRET_AUDIO_INTERVAL]
        if not interval or not interval.isdigit() or int(interval) < int(Constants.MAX_AUDIO_INTERVAL_SECONDS):
            interval = Constants.MAX_AUDIO_INTERVAL_SECONDS

        context = {"interval": interval, "patient_id": qp["patient_id"], "note_id": qp["note_id"]}
        return [
            HTMLResponse(render_to_string("templates/capture_tuning_case.html", context), status_code=HTTPStatus.OK),
        ]

    def post(self) -> list[Response | Effect]:
        client_s3 = AwsS3(AwsS3Credentials.from_dictionary_tuning(self.secrets))
        subdomain = self.request.headers["host"].split(".")[0]
        if bool(self.request.query_params.get("archive_limited_chart")):
            result = ArchiverHelper.store_chart(client_s3, subdomain, self.request)
        else:
            result = ArchiverHelper.store_audio(client_s3, subdomain, self.request)
        return [result]


class ArchiverHelper:
    @classmethod
    def store_chart(cls, client_s3: AwsS3, subdomain: str, request: Request) -> JSONResponse:
        patient_id = request.query_params["patient_id"]
        note_id = request.query_params["note_id"]
        identification = IdentificationParameters(
            patient_uuid=patient_id,
            note_uuid=note_id,
            provider_uuid=str(Note.objects.get(id=note_id).provider.id),
            canvas_instance="",
        )
        limited_chart = (
            LimitedCacheLoader(
                identification,
                AccessPolicy.allow_all(),
                True,
            )
            .load_from_database()
            .to_json()
        )
        object_key = f"hyperscribe-{subdomain}/patient_{patient_id}/note_{note_id}/limited_chart.json"
        response = client_s3.upload_text_to_s3(object_key, json.dumps(limited_chart))
        return JSONResponse({"s3status": response.status_code, "s3text": response.text, "s3key": object_key})

    @classmethod
    def store_audio(cls, client_s3: AwsS3, subdomain: str, request: Request) -> JSONResponse:
        form_data = request.form_data()
        audio_form_part = form_data.get("audio")
        if audio_form_part is None:
            return JSONResponse({"message": "Form data must include 'audio' part"}, HTTPStatus.BAD_REQUEST)

        file_name = (
            audio_form_part.filename.replace("_note", "/note")
            .replace("_chunk", "/chunk")
            .replace(".webm", f"_{int(time())}.webm")
        )
        object_key = f"hyperscribe-{subdomain}/{file_name}"
        response = client_s3.upload_binary_to_s3(object_key, audio_form_part.content, audio_form_part.content_type)
        return JSONResponse({"s3status": response.status_code, "s3text": response.text, "s3key": object_key})
