from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


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
