import json
from os import environ

from canvas_sdk.v1.data import Note

from evaluations.constants import Constants
from evaluations.structures.postgres_credentials import PostgresCredentials
from hyperscribe.libraries.constants import Constants as HyperscribeConstants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings


class HelperEvaluation:

    @classmethod
    def settings(cls) -> Settings:
        return Settings.from_dictionary(dict(environ))

    @classmethod
    def aws_s3_credentials(cls) -> AwsS3Credentials:
        return AwsS3Credentials.from_dictionary(dict(environ))

    @classmethod
    def postgres_credentials(cls) -> PostgresCredentials:
        return PostgresCredentials.from_dictionary(dict(environ))

    @classmethod
    def get_note_uuid(cls, patient_uuid: str) -> str:
        note = Note.objects.filter(patient__id=patient_uuid).order_by("-dbid").first()  # the last note
        return str(note.id)

    @classmethod
    def get_provider_uuid(cls, patient_uuid: str) -> str:
        note = Note.objects.filter(patient__id=patient_uuid).order_by("-dbid").first()  # the last note
        return str(note.provider.id)

    @classmethod
    def get_canvas_instance(cls) -> str:
        return environ.get(HyperscribeConstants.CUSTOMER_IDENTIFIER) or "EvaluationBuilderInstance"

    @classmethod
    def json_schema_differences(cls) -> dict:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": Constants.DIFFERENCE_LEVELS},
                    "difference": {"type": "string", "description": "description of the difference between the JSONs"},
                },
                "required": ["level", "difference"],
            }
        }

    @classmethod
    def json_nuanced_differences(cls, case: str, accepted_levels: list[str], result_json: str, expected_json: str) -> tuple[bool, str]:
        system_prompt = [
            "The user will provides two JSON objects.",
            "Your task is compare them and report the discrepancies as a JSON list in a Markdown block like:",
            "```json",
            json.dumps([
                {
                    "level": f'one of: {",".join(Constants.DIFFERENCE_LEVELS)}',
                    "difference": "description of the difference between the JSONs",
                }
            ]),
            "```",
            "",
            # "All text values should be considered on the levels scale in order to solely express the meaning differences.",
            "All text values should be evaluated together and on the level scale to effectively convey the impact of the changes in meaning from a medical point of view.",
            f"Any key with the value '{Constants.IGNORED_KEY_VALUE}' should be ignored.",
            "Unless otherwise specified, dates and numbers must be presented identically.",
        ]
        user_prompt = [
            "First JSON, called 'automated': ",
            "```json",
            result_json,
            "```",
            "",
            "Second JSON, called 'reviewed': ",
            "```json",
            expected_json,
            "```",
            "",
            "Please, review both JSONs and report as instructed all differences.",
        ]
        return cls.nuanced_differences(case, accepted_levels, system_prompt, user_prompt)

    @classmethod
    def text_nuanced_differences(cls, case: str, accepted_levels: list[str], result_text: str, expected_text: str) -> tuple[bool, str]:
        system_prompt = [
            "The user will provides two texts.",
            "Your task is compare them *solely* from a medical meaning point of view and report the discrepancies as a JSON list in a Markdown block like:",
            "```json",
            json.dumps([
                {
                    "level": f'one of: {",".join(Constants.DIFFERENCE_LEVELS)}',
                    "difference": "description of the difference between the texts",
                }
            ]),
            "```",
        ]
        user_prompt = [
            "First text, called 'automated': ",
            "```text",
            result_text,
            "```",
            "",
            "Second text, called 'reviewed': ",
            "```text",
            expected_text,
            "```",
            "",
            "Please, review both texts and report as instructed all differences from a meaning point of view.",
        ]
        return cls.nuanced_differences(case, accepted_levels, system_prompt, user_prompt)

    @classmethod
    def nuanced_differences(cls, case: str, accepted_levels: list[str], system_prompt: list[str], user_prompt: list[str]) -> tuple[bool, str]:
        identification = IdentificationParameters(
            patient_uuid=HyperscribeConstants.FAUX_PATIENT_UUID,
            note_uuid=HyperscribeConstants.FAUX_NOTE_UUID,
            provider_uuid=HyperscribeConstants.FAUX_PROVIDER_UUID,
            canvas_instance=cls.get_canvas_instance(),
        )
        conversation = Helper.chatter(cls.settings(), MemoryLog(identification, case))
        conversation.set_system_prompt(system_prompt)
        conversation.set_user_prompt(user_prompt)
        chat = conversation.chat([cls.json_schema_differences()])
        if chat.has_error:
            return False, f"encountered error: {chat.error}"

        excluded_minor_differences = [
            difference
            for difference in chat.content[0]
            if difference["level"] not in accepted_levels
        ]
        return bool(excluded_minor_differences == []), json.dumps(chat.content, indent=1)
