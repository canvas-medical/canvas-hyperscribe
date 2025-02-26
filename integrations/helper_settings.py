import json
from os import environ

from canvas_sdk.v1.data import Note

from commander.protocols.commander import Commander
from commander.protocols.helper import Helper
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


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
    def get_note_uuid(cls, patient_uuid: str) -> str:
        note = Note.objects.filter(patient__id=patient_uuid).order_by("-dbid").first()  # the last note
        return str(note.id)

    @classmethod
    def get_provider_uuid(cls, patient_uuid: str) -> str:
        note = Note.objects.filter(patient__id=patient_uuid).order_by("-dbid").first()  # the last note
        return str(note.provider.id)

    @classmethod
    def json_nuanced_differences(cls, accepted_levels: list[str], result_json: str, expected_json: str) -> tuple[bool, str]:
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
        return cls.nuanced_differences(accepted_levels, system_prompt, user_prompt)

    @classmethod
    def text_nuanced_differences(cls, accepted_levels: list[str], result_text: str, expected_text: str) -> tuple[bool, str]:
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
        return cls.nuanced_differences(accepted_levels, system_prompt, user_prompt)

    @classmethod
    def nuanced_differences(cls, accepted_levels: list[str], system_prompt: list[str], user_prompt: list[str]) -> tuple[bool, str]:
        settings = cls.settings()
        conversation = Helper.chatter(settings)
        conversation.set_system_prompt(system_prompt)
        conversation.set_user_prompt(user_prompt)
        chat = conversation.chat()
        if chat.has_error:
            return False, f"encountered error: {chat.error}"
        excluded_minor_differences = [
            difference
            for difference in chat.content
            if difference["level"] not in accepted_levels
        ]
        return bool(excluded_minor_differences == []), json.dumps(chat.content, indent=1)
