from enum import Enum

from canvas_sdk.commands.commands.questionnaire import ResponseOption


class QuestionType(Enum):
    TYPE_TEXT = ResponseOption.TYPE_TEXT
    TYPE_INTEGER = ResponseOption.TYPE_INTEGER
    TYPE_RADIO = ResponseOption.TYPE_RADIO
    TYPE_CHECKBOX = ResponseOption.TYPE_CHECKBOX

    @classmethod
    def llm_readable(cls) -> dict:
        return {
            cls.TYPE_TEXT: "free text",
            cls.TYPE_INTEGER: "integer",
            cls.TYPE_RADIO: "single choice",
            cls.TYPE_CHECKBOX: "multiple choice",
        }
