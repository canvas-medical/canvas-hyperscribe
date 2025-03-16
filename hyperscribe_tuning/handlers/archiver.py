from hashlib import sha256
from http import HTTPStatus
from time import time

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, JSONResponse, Response
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from canvas_sdk.templates import render_to_string

from hyperscribe_tuning.handlers.aws_s3 import AwsS3
from hyperscribe_tuning.handlers.constants import Constants


class Archiver(SimpleAPIRoute):
    PATH = "/archive"

    def authenticate(self, credentials: Credentials) -> bool:
        query_params = self.request.query_params

        # Need signing params
        if 'ts' not in query_params or 'sig' not in query_params:
            return False

        timestamp = int(query_params['ts'])

        # No good if more than one hour old
        if (time() - timestamp) > Constants.MAX_AUTHENTICATION_TIME:
            return False

        request_sig = query_params['sig']
        hash_arg = query_params['ts'] + self.secrets[Constants.SECRET_API_SIGNING_KEY]
        internal_sig = sha256(hash_arg.encode('utf-8')).hexdigest()

        return request_sig == internal_sig

    def get(self) -> list[Response | Effect]:
        qp = self.request.query_params

        # force the interval to 15s or more
        interval = self.secrets[Constants.SECRET_AUDIO_INTERVAL_SECONDS]
        if not interval or not interval.isdigit() or int(interval) < int(Constants.MAX_AUDIO_INTERVAL_SECONDS):
            interval = Constants.MAX_AUDIO_INTERVAL_SECONDS

        context = {
            'interval': interval,
            'patient_id': qp['patient_id'],
            'note_id': qp['note_id'],
        }
        return [
            HTMLResponse(
                render_to_string('templates/capture_tuning_case.html', context),
                status_code=HTTPStatus.OK,
            )
        ]

    def post(self) -> list[Response | Effect]:
        client_s3 = AwsS3(
            self.secrets[Constants.SECRET_AWS_KEY],
            self.secrets[Constants.SECRET_AWS_SECRET],
            self.secrets[Constants.SECRET_AWS_REGION],
            self.secrets[Constants.SECRET_AWS_BUCKET],
        )

        form_data = self.request.form_data()

        audio_form_part = form_data.get('audio')
        if audio_form_part is None:
            return JSONResponse(
                {"message": "Form data must include 'audio' part"}, 
                HTTPStatus.BAD_REQUEST,
            )

        file_name = (audio_form_part.filename
                     .replace('_note', '/note')
                     .replace('_chunk', '/chunk')
                     .replace('.webm', f'_{int(time())}.webm'))
        subdomain = self.request.headers['host'].split('.')[0]
        object_key = f"{subdomain}/{file_name}"
        resp = client_s3.upload_binary_to_s3(
            object_key,
            audio_form_part.content,
            audio_form_part.content_type,
        )

        return [
            JSONResponse({
                "s3status": resp.status_code,
                "s3text": resp.text,
                "s3key": object_key,
            })
        ]
