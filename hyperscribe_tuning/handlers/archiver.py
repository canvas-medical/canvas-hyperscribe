# from __future__ import annotations
import time
from http import HTTPStatus
from hashlib import sha256

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import HTMLResponse, JSONResponse, Response
from canvas_sdk.templates import render_to_string
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute

from hyperscribe_tuning.handlers.aws_s3 import AwsS3


class HyperscribeTuningAPI(SimpleAPIRoute):
    PATH = "/capture-case"

    def authenticate(self, credentials: Credentials) -> bool:
        query_params = self.request.query_params

        # Need signing params
        if 'ts' not in query_params or 'sig' not in query_params:
            return False
        
        timestamp = int(query_params['ts'])

        # No good if more than one hour old
        if (time.time() - timestamp) > (3600):
            return False
        
        request_sig = query_params['sig']
        hash_arg = query_params['ts'] + self.secrets['APISigningKey']
        internal_sig = sha256(hash_arg.encode('utf-8')).hexdigest()
        
        return request_sig == internal_sig

    def get(self) -> list[Response | Effect]:
        qp = self.request.query_params
        context = {
            'interval': self.secrets['AudioIntervalSeconds'] or '15',  # default 15s
            'patient_id': qp['patient_id'],
            'note_id': qp['note_id']
        }
        return [
            HTMLResponse(
                render_to_string(f'templates/capture_tuning_case.html', context),
                status_code=HTTPStatus.OK
            )
        ]

    def post(self) -> list[Response | Effect]:
        client_s3 = AwsS3(
            self.secrets["AwsKey"],
            self.secrets["AwsSecret"],
            self.secrets["AwsRegion"],
            self.secrets["AwsBucket"],
        )
        
        form_data = self.request.form_data()
        audio_form_part = form_data.get('audio')
        file_name = (audio_form_part.filename
                     .replace('_note', '/note')
                     .replace('_chunk', '/chunk'))
        subdomain = self.request.headers['host'].split('.')[0]
        object_key = f"{subdomain}/{file_name}"
        resp = client_s3.upload_binary_to_s3(
            object_key, audio_form_part.content, audio_form_part.content_type)
        
        return [
            JSONResponse({
                "s3_status": resp.status_code,
                "s3_txt": resp.text
            })
        ]
