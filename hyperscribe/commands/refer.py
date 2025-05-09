from canvas_sdk.commands import ReferCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Refer(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REFER

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (refer_to := data.get("refer_to")) and (text := refer_to.get("text")):
            priority = data.get('priority') or "n/a"
            question = data.get('clinical_question') or "n/a"
            notes_to_specialist = data.get('notes_to_specialist') or "n/a"
            indications = "/".join([
                indication
                for question in (data.get("indications") or [])
                if (indication := question.get("text"))
            ]) or "n/a"
            documents = "/".join([
                document
                for included in (data.get("documents_to_include") or [])
                if (document := included.get("text"))
            ]) or "n/a"
            return CodedItem(
                label=f"referred to {text}: {notes_to_specialist} (priority: {priority}, question: {question}, "
                      f"documents: {documents}, related conditions: {indications})",
                code="",
                uuid="",
            )
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        zip_codes = self.practice_setting("serviceAreaZipCodes")
        information = instruction.parameters["referredServiceProvider"]["specialty"]
        if names := instruction.parameters["referredServiceProvider"]["names"]:
            information = f"{information} {names}"  # <-- the order is important for the search in the Canvas Science service

        provider = SelectorChat.contact_from(instruction, chatter, self.settings, information, zip_codes)
        result = ReferCommand(
            service_provider=provider,
            clinical_question=Helper.enum_or_none(instruction.parameters["clinicalQuestions"], ReferCommand.ClinicalQuestion),
            priority=Helper.enum_or_none(instruction.parameters["priority"], ReferCommand.Priority),
            notes_to_specialist=instruction.parameters["notesToSpecialist"],
            comment=instruction.parameters["comment"],
            note_uuid=self.identification.note_uuid,
            diagnosis_codes=[],
        )
        # retrieve the linked conditions
        conditions = []
        for condition in instruction.parameters["conditions"]:
            item = SelectorChat.condition_from(
                instruction,
                chatter,
                self.settings,
                condition["conditionKeywords"].split(","),
                condition["ICD10"].split(","),
                instruction.parameters["comment"],
            )
            if item.code:
                conditions.append(item)
                result.diagnosis_codes.append(item.code)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        questions = ", ".join([f"'{item.value}'" for item in ReferCommand.ClinicalQuestion])
        priorities = "/".join([item.value for item in ReferCommand.Priority])
        return {
            "referredServiceProvider": {
                "specialty": "the specialty of the referred provider, required",
                "names": "the names of the practice and/or of the referred provider, or empty",
            },
            "clinicalQuestions": f"one of: {questions}",
            "priority": f"one of: {priorities}",
            "notesToSpecialist": "note or question to be sent to the referred specialist, required, as concise free text",
            "comment": "rationale of the referral, as free text",
            "conditions": [
                {
                    "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition related to the referral",
                    "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition related to the referral",
                },
            ],
        }

    def instruction_description(self) -> str:
        return ("Referral to a specialist, including the rationale and the targeted conditions. "
                "There can be only one referral in an instruction with all necessary information, "
                "and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
