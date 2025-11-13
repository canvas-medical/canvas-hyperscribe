import json
from datetime import datetime

from hyperscribe.handlers.progress_display import ProgressDisplay
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.structures.model_spec import ModelSpec
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.settings import Settings


class LlmDecisionsReviewer:
    @classmethod
    def review(
        cls,
        identification: IdentificationParameters,
        settings: Settings,
        credentials: AwsS3Credentials,
        command2uuid: dict,
        created: datetime,
        cycles: int,
    ) -> None:
        # no audit expected
        if settings.audit_llm is False:
            return
        # no AWS credentials
        client_s3 = AwsS3(credentials)
        if client_s3.is_ready() is False:
            return
        # audit already performed
        store_path = f"hyperscribe-{identification.canvas_instance}/audits/{identification.note_uuid}/"
        if client_s3.list_s3_objects(store_path):
            return

        #
        cached = CachedSdk.get_discussion(identification.note_uuid)
        cached.created = created
        cached.cycle = cycles + 1  # to force the new logs in a subsequent folder
        cached.save()
        creation_day = cached.creation_day()

        messages = [
            ProgressMessage(
                message="create the audits...",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(identification, settings, messages)
        for cycle in range(1, cycles + 1):
            result: list[dict] = []
            store = LlmTurnsStore(credentials, identification, creation_day, cycle)
            for incremented_step, discussion in store.stored_documents():
                messages = [
                    ProgressMessage(
                        message=f"auditing of {incremented_step} (cycle {cycle: 02d})",
                        section=Constants.PROGRESS_SECTION_TECHNICAL,
                    )
                ]
                ProgressDisplay.send_to_user(identification, settings, messages)
                indexed_command, increment = LlmTurnsStore.decompose(incremented_step)
                chatter = Helper.chatter(
                    settings,
                    MemoryLog.instance(identification, f"audit_{incremented_step}", credentials),
                    ModelSpec.COMPLEX,
                )
                system_prompt: list[str] = []
                model_prompt: list[str] = []
                for prompt in LlmTurn.load_from_json(discussion):
                    chatter.add_prompt(prompt)
                    if prompt.role == LlmBase.ROLE_SYSTEM:
                        system_prompt = prompt.text  # should have only one
                    elif prompt.role == LlmBase.ROLE_MODEL:
                        model_prompt = prompt.text  # use the last one

                details = []
                if incremented_step.lower().startswith("transcript2instructions"):
                    details.append("Mention specific parts of the transcript to support the rationale.")
                    if increment > 0:
                        details.append(
                            "Report only the items with changed value between your last response and the ones you "
                            "provided before.",
                        )
                if incremented_step.lower().startswith("questionnaire"):
                    details.append(
                        "Report only the items with changed value and mention specific parts of the transcript to "
                        "support the rationale.",
                    )

                audit_schema = JsonSchema.get(["audit_with_value"])[0]
                user_prompt = [
                    "Your task is now to explain the rationale of each and every value you have provided, citing "
                    "any text or value you used.",
                    "\n".join(details),
                    "Present the reasoning behind each and every value you provided, your response should be a JSON "
                    "following this JSON Schema:",
                    "```json",
                    json.dumps(audit_schema),
                    "```",
                    "",
                ]
                audit = chatter.single_conversation(system_prompt, user_prompt, [audit_schema], None)
                result.append(
                    {
                        "uuid": command2uuid.get(indexed_command) or incremented_step,
                        "command": indexed_command,
                        "increment": increment,
                        "decision": model_prompt,
                        "audit": audit,
                    },
                )
            store_path = (
                f"hyperscribe-{identification.canvas_instance}/"
                "audits/"
                f"{identification.note_uuid}/"
                f"final_audit_{cycle:02d}.log"
            )
            client_s3.upload_text_to_s3(store_path, json.dumps(result, indent=2))
        messages = [
            ProgressMessage(
                message="audits done",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(identification, settings, messages)
