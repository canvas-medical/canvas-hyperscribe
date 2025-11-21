import json
from http import HTTPStatus

from canvas_sdk.effects.simple_api import Response

from hyperscribe.commands.follow_up import FollowUp
from hyperscribe.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.commands.instruct import Instruct
from hyperscribe.commands.plan import Plan
from hyperscribe.commands.reason_for_visit import ReasonForVisit
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.customization import Customization as UserOptions
from hyperscribe.structures.default_tab import DefaultTab


class Customization:
    CUSTOM_PROMPT_COMMANDS = [
        command.class_name()
        for command in [
            FollowUp,
            HistoryOfPresentIllness,
            Instruct,
            Plan,
            ReasonForVisit,
        ]
    ]

    @classmethod
    def customizations(cls, aws_s3: AwsS3Credentials, canvas_instance: str, user_id: str) -> UserOptions:
        result = UserOptions(
            custom_prompts=[
                CustomPrompt(command=command, prompt="", active=False) for command in cls.CUSTOM_PROMPT_COMMANDS
            ],
            ui_default_tab=DefaultTab.TRANSCRIPT,
        )
        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            customizations = client_s3.access_s3_object(cls.aws_customizations(canvas_instance, user_id))
            if customizations.status_code == HTTPStatus.OK:
                result = UserOptions.load_from_json(customizations.json())
            else:
                # TODO 2025-11-21 remove this else after the code is deployed and
                #  users have created their customizations (this is a convenience)
                result = UserOptions(
                    custom_prompts=cls.custom_prompts(aws_s3, canvas_instance, user_id),
                    ui_default_tab=DefaultTab.TRANSCRIPT,
                )

        return result

    @classmethod
    def save_ui_default_tab(
        cls,
        aws_s3: AwsS3Credentials,
        canvas_instance: str,
        user_id: str,
        ui_default_tab: DefaultTab,
    ) -> Response:
        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            customizations = cls.customizations(aws_s3, canvas_instance, user_id)
            return client_s3.upload_text_to_s3(
                cls.aws_customizations(canvas_instance, user_id),
                json.dumps(
                    UserOptions(
                        custom_prompts=customizations.custom_prompts,
                        ui_default_tab=ui_default_tab,
                    ).to_dict()
                ),
            )
        return Response(b"Store not ready", status_code=HTTPStatus.UNAUTHORIZED)

    @classmethod
    def save_custom_prompt(
        cls,
        aws_s3: AwsS3Credentials,
        canvas_instance: str,
        user_id: str,
        custom_prompt: CustomPrompt,
    ) -> Response:
        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            if custom_prompt.command in cls.CUSTOM_PROMPT_COMMANDS:
                customizations = cls.customizations(aws_s3, canvas_instance, user_id)
                custom_prompts = {item.command: item for item in customizations.custom_prompts} | {
                    custom_prompt.command: custom_prompt,
                }
                return client_s3.upload_text_to_s3(
                    cls.aws_customizations(canvas_instance, user_id),
                    json.dumps(
                        UserOptions(
                            custom_prompts=list(custom_prompts.values()),
                            ui_default_tab=customizations.ui_default_tab,
                        ).to_dict()
                    ),
                )
        return Response(b"Store not ready", status_code=HTTPStatus.UNAUTHORIZED)

    @classmethod
    def aws_customizations(cls, canvas_instance: str, user_id: str) -> str:
        return f"hyperscribe-{canvas_instance}/customizations/customizations_{user_id}.json"

    @classmethod
    def custom_prompts_as_secret(cls, aws_s3: AwsS3Credentials, canvas_instance: str, user_id: str) -> dict:
        return {
            Constants.SECRET_CUSTOM_PROMPTS: json.dumps(
                [item.to_json() for item in cls.customizations(aws_s3, canvas_instance, user_id).custom_prompts]
            )
        }

    # TODO 2025-11-21 the code below (until '^^^') should be removed after the code above is deployed
    #  vvv
    @classmethod
    def custom_prompts(cls, aws_s3: AwsS3Credentials, canvas_instance: str, user_id: str) -> list[CustomPrompt]:
        result: list[CustomPrompt] = []
        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            # TODO 2025-11-20 remove the "" item (and thus the loop) after the code is deployed and
            #  users have created their own prompts (this is a convenience)
            for item in [user_id, ""]:
                custom_prompts = client_s3.access_s3_object(cls.aws_custom_prompts(canvas_instance, item))
                if custom_prompts.status_code == HTTPStatus.OK:
                    result = CustomPrompt.load_from_json_list(custom_prompts.json())
                    break

        if not result:
            return [CustomPrompt(command=command, prompt="", active=False) for command in cls.CUSTOM_PROMPT_COMMANDS]
        return result

    @classmethod
    def aws_custom_prompts(cls, canvas_instance: str, user_id: str) -> str:
        # TODO 2025-11-20 remove the if (user_id should never be empty) after the code is deployed and
        #  users have created their own prompts (this is a convenience)
        if user_id:
            return f"hyperscribe-{canvas_instance}/customizations/custom_prompts_{user_id}.json"
        return f"hyperscribe-{canvas_instance}/customizations/custom_prompts.json"

    # TODO
    #  ^^^
