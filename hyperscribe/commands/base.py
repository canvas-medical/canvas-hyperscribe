from typing import Any

from canvas_sdk.v1.data import PracticeLocation, Staff

from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings


class Base:

    def __init__(self, settings: Settings, cache: LimitedCache, identification: IdentificationParameters):
        self.settings = settings
        self.identification = identification
        self.cache = cache

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    @classmethod
    def schema_key(cls) -> str:
        raise NotImplementedError

    @classmethod
    def staged_command_extract(cls, data: dict) -> CodedItem | None:
        raise NotImplementedError

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        raise NotImplementedError

    def command_parameters(self) -> dict:
        raise NotImplementedError

    def instruction_description(self) -> str:
        raise NotImplementedError

    def instruction_constraints(self) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    def practice_setting(self, setting: str) -> Any:
        practice = Staff.objects.get(id=self.identification.provider_uuid).primary_practice_location
        if practice is None:
            practice = PracticeLocation.objects.order_by("dbid").first()
        if practice and (setting := practice.settings.filter(name=setting).order_by("dbid").first()):
            return setting.value
        return None
