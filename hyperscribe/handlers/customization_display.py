import json
from http import HTTPStatus

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials, api

from hyperscribe.commands.follow_up import FollowUp
from hyperscribe.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.commands.instruct import Instruct
from hyperscribe.commands.plan import Plan
from hyperscribe.commands.reason_for_visit import ReasonForVisit
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials


class CustomizationDisplay(SimpleAPI):
    PREFIX = None

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    @api.get("/customization/commands")
    def command_list(self) -> list[Response | Effect]:
        return [JSONResponse(self.custom_prompts(), status_code=HTTPStatus.OK)]

    @api.post("/customization/command")
    def command_save(self) -> list[Response | Effect]:
        content = self.request.json()
        result = self.save_custom_prompts(content["command"], content["customPrompt"])
        return [
            JSONResponse(
                {"response": result.content.decode("utf-8") or str(result.status_code)},
                status_code=HTTPStatus(result.status_code),
            )
        ]

    def save_custom_prompts(self, command: str, custom_prompt: str) -> Response:
        client_s3 = AwsS3(AwsS3Credentials.from_dictionary(self.secrets))
        if client_s3.is_ready():
            current = self.custom_prompts()
            if command in current:
                current[command] = custom_prompt
                return client_s3.upload_text_to_s3(self.aws_custom_prompts(), json.dumps(current))
        return Response(b"Store not ready", status_code=HTTPStatus.UNAUTHORIZED)

    def custom_prompts(self) -> dict:
        result = {
            FollowUp.class_name(): "",
            HistoryOfPresentIllness.class_name(): "",
            Instruct.class_name(): "",
            Plan.class_name(): "",
            ReasonForVisit.class_name(): "",
        }
        client_s3 = AwsS3(AwsS3Credentials.from_dictionary(self.secrets))
        if client_s3.is_ready():
            custom_prompts = client_s3.access_s3_object(self.aws_custom_prompts())
            if custom_prompts.status_code == HTTPStatus.OK:
                result |= custom_prompts.json()
        return result

    def aws_custom_prompts(self) -> str:
        return f"hyperscribe-{self.environment[Constants.CUSTOMER_IDENTIFIER]}/customizations/custom_prompts.json"
