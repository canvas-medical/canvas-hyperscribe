from http import HTTPStatus

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials, api

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.customization import Customization
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.custom_prompt import CustomPrompt


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
        user_id = self.request.headers.get("canvas-logged-in-user-id")
        user_type = self.request.headers.get("canvas-logged-in-user-type")
        if user_type != Constants.USER_TYPE_STAFF:
            return []
        return [
            JSONResponse(
                [
                    item.to_json()
                    for item in Customization.custom_prompts(
                        AwsS3Credentials.from_dictionary(self.secrets),
                        self.environment[Constants.CUSTOMER_IDENTIFIER],
                        user_id,
                    )
                ],
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/customization/command")
    def command_save(self) -> list[Response | Effect]:
        user_id = self.request.headers.get("canvas-logged-in-user-id")
        user_type = self.request.headers.get("canvas-logged-in-user-type")
        if user_type != Constants.USER_TYPE_STAFF:
            return []
        content = self.request.json()
        result = Customization.save_custom_prompt(
            AwsS3Credentials.from_dictionary(self.secrets),
            self.environment[Constants.CUSTOMER_IDENTIFIER],
            CustomPrompt.load_from_json(content),
            user_id,
        )
        return [
            JSONResponse(
                {"response": result.content.decode("utf-8") or str(result.status_code)},
                status_code=HTTPStatus(result.status_code),
            )
        ]
