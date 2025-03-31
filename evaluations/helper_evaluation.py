import json
from os import environ
from pathlib import Path

from canvas_sdk.v1.data import Note

from evaluations.structures.postgres_credentials import PostgresCredentials
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.settings import Settings


class HelperEvaluation:
    DIFFERENCE_LEVELS = ["minor", "moderate", "severe", "critical"]

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
    def json_nuanced_differences(cls, case: str, accepted_levels: list[str], result_json: str, expected_json: str) -> tuple[bool, str]:
        system_prompt = [
            "The user will provides two JSON objects.",
            "Your task is compare them and report the discrepancies as a JSON list in a Markdown block like:",
            "```json",
            json.dumps([
                {
                    "level": "/".join(cls.DIFFERENCE_LEVELS),
                    "difference": "description of the difference between the JSONs",
                }
            ]),
            "```",
            "",
            # "All text values should be considered on the levels scale in order to solely express the meaning differences.",
            "All text values should be evaluated together and on the level scale to effectively convey the impact of the changes in meaning from a medical point of view.",
            "Any key with the value '>?<' should be ignored.",
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
                    "level": "/".join(cls.DIFFERENCE_LEVELS),
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
        conversation = Helper.chatter(cls.settings(), MemoryLog("theNoteUuid", case))
        conversation.set_system_prompt(system_prompt)
        conversation.set_user_prompt(user_prompt)
        with (Path(__file__).parent / "schema_differences.json").open("r") as f:
            chat = conversation.chat([json.load(f)])
            if chat.has_error:
                return False, f"encountered error: {chat.error}"
            excluded_minor_differences = [
                difference
                for difference in chat.content
                if difference["level"] not in accepted_levels
            ]
            return bool(excluded_minor_differences == []), json.dumps(chat.content, indent=1)
