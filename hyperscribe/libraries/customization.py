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
    def custom_prompts(cls, aws_s3: AwsS3Credentials, canvas_instance: str) -> list[CustomPrompt]:
        result: list[CustomPrompt] = []
        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            custom_prompts = client_s3.access_s3_object(cls.aws_custom_prompts(canvas_instance))
            if custom_prompts.status_code == HTTPStatus.OK:
                result = CustomPrompt.load_from_json_list(custom_prompts.json())
        if not result:
            return [CustomPrompt(command=command, prompt="", active=False) for command in cls.CUSTOM_PROMPT_COMMANDS]
        return result

    @classmethod
    def save_custom_prompt(
        cls,
        aws_s3: AwsS3Credentials,
        canvas_instance: str,
        custom_prompt: CustomPrompt,
    ) -> Response:
        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            if custom_prompt.command in cls.CUSTOM_PROMPT_COMMANDS:
                current = {item.command: item for item in cls.custom_prompts(aws_s3, canvas_instance)} | {
                    custom_prompt.command: custom_prompt,
                }
                return client_s3.upload_text_to_s3(
                    cls.aws_custom_prompts(canvas_instance),
                    json.dumps([item.to_json() for item in current.values()]),
                )
        return Response(b"Store not ready", status_code=HTTPStatus.UNAUTHORIZED)

    @classmethod
    def aws_custom_prompts(cls, canvas_instance: str) -> str:
        return f"hyperscribe-{canvas_instance}/customizations/custom_prompts.json"

    @classmethod
    def custom_prompts_as_secret(cls, aws_s3: AwsS3Credentials, canvas_instance: str) -> dict:
        return {
            Constants.SECRET_CUSTOM_PROMPTS: json.dumps(
                [item.to_json() for item in cls.custom_prompts(aws_s3, canvas_instance)]
            )
        }
