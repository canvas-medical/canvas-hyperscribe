import json
from os import environ
from pathlib import Path

from canvas_sdk.v1.data import Note

from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.handlers.structures.settings import Settings
from hyperscribe.handlers.structures.vendor_key import VendorKey


class HelperSettings:
    DIFFERENCE_LEVELS = ["minor", "moderate", "severe", "critical"]

    @classmethod
    def settings(cls) -> Settings:
        return Settings(
            llm_text=VendorKey(
                vendor=environ[Commander.SECRET_TEXT_VENDOR],
                api_key=environ[Commander.SECRET_TEXT_KEY],
            ),
            llm_audio=VendorKey(
                vendor=environ[Commander.SECRET_AUDIO_VENDOR],
                api_key=environ[Commander.SECRET_AUDIO_KEY],
            ),
            science_host=environ[Commander.SECRET_SCIENCE_HOST],
            ontologies_host=environ[Commander.SECRET_ONTOLOGIES_HOST],
            pre_shared_key=environ[Commander.SECRET_PRE_SHARED_KEY],
            structured_rfv=bool(environ[Commander.SECRET_STRUCTURED_RFV].lower() in ["yes", "y", "1"]),
        )

    @classmethod
    def flush_log(cls, note_uuid: str, log_path: str) -> None:
        aws_key = environ.get(Commander.SECRET_AWS_KEY)
        aws_secret = environ.get(Commander.SECRET_AWS_SECRET)
        region = environ.get(Commander.SECRET_AWS_REGION)
        bucket = environ.get(Commander.SECRET_AWS_BUCKET)
        if aws_key and aws_secret and region and bucket:
            client_s3 = AwsS3(aws_key, aws_secret, region, bucket)
            client_s3.upload_text_to_s3(log_path, MemoryLog.end_session(note_uuid))

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
