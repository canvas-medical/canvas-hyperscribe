from __future__ import annotations

import json
from datetime import datetime

from canvas_sdk.effects import Effect
from canvas_sdk.events import EventType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.v1.data import TaskComment
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

from hyperscribe.handlers.progress import Progress
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.comment_body import CommentBody
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings


class Reviewer(BaseProtocol):
    RESPONDS_TO = [
        # TODO when https://github.com/canvas-medical/canvas-plugins/issues/600 is fixed,
        #  just used the TASK_COMPLETED event
        EventType.Name(EventType.TASK_COMMENT_CREATED),
        # EventType.Name(EventType.TASK_COMPLETED),
    ]

    def compute(self) -> list[Effect]:
        comment = TaskComment.objects.get(id=self.target)
        if not comment.task.labels.filter(name=Constants.LABEL_ENCOUNTER_COPILOT).first():
            return []
        information = CommentBody.load_from_json(json.loads(comment.body))
        if information.finished is None:
            return []

        note = Note.objects.get(id=information.note_id)
        identification = IdentificationParameters(
            patient_uuid=note.patient.id,
            note_uuid=information.note_id,
            provider_uuid=str(note.provider.id),
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        log.info("  => create the final audit")
        self.compute_audit_documents(identification, information.created, information.chunk_index)

        return []

    def compute_audit_documents(self, identification: IdentificationParameters, created: datetime, cycles: int) -> None:
        mapping = ImplementedCommands.schema_key2instruction()
        command2uuid = {
            LlmTurnsStore.indexed_instruction(mapping[command.schema_key], index): str(command.id)
            for index, command in enumerate(
                Command.objects.filter(
                    patient__id=identification.patient_uuid,
                    note__id=identification.note_uuid,
                    state="staged",  # <--- TODO use an Enum when provided
                ).order_by("dbid"),
            )
        }

        settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
        credentials = AwsS3Credentials.from_dictionary(self.secrets)
        LlmDecisionsReviewer.review(identification, settings, credentials, command2uuid, created, cycles)
        Progress.send_to_user(identification, settings, Constants.PROGRESS_END_OF_MESSAGES)
