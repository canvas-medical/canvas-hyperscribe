from http import HTTPStatus

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials, api

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.customization import Customization
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.default_tab import DefaultTab


class CustomizationDisplay(SimpleAPI):
    PREFIX = None

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    @api.get("/customization/all")
    def customizations(self) -> list[Response | Effect]:
        user_id = self.request.headers.get("canvas-logged-in-user-id")
        user_type = self.request.headers.get("canvas-logged-in-user-type")
        if user_type != Constants.USER_TYPE_STAFF:
            return []

        customizations = Customization.customizations(
            AwsS3Credentials.from_dictionary(self.secrets),
            self.environment[Constants.CUSTOMER_IDENTIFIER],
            user_id,
        )
        return [JSONResponse(customizations.to_dict(), status_code=HTTPStatus.OK)]

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
            user_id,
            CustomPrompt.load_from_json(content),
        )
        return [
            JSONResponse(
                {"response": result.content.decode("utf-8") or str(result.status_code)},
                status_code=HTTPStatus(result.status_code),
            )
        ]

    @api.post("/customization/ui_default_tab")
    def ui_default_tab_save(self) -> list[Response | Effect]:
        user_id = self.request.headers.get("canvas-logged-in-user-id")
        user_type = self.request.headers.get("canvas-logged-in-user-type")
        if user_type != Constants.USER_TYPE_STAFF:
            return []
        content = self.request.json()
        result = Customization.save_ui_default_tab(
            AwsS3Credentials.from_dictionary(self.secrets),
            self.environment[Constants.CUSTOMER_IDENTIFIER],
            user_id,
            DefaultTab(content["uiDefaultTab"]),
        )
        return [
            JSONResponse(
                {"response": result.content.decode("utf-8") or str(result.status_code)},
                status_code=HTTPStatus(result.status_code),
            )
        ]
