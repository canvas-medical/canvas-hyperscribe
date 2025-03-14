from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.v1.data import PracticeLocation

from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.settings import Settings


class Base:

    def __init__(self, settings: Settings, cache: LimitedCache, patient_uuid: str, note_uuid: str, provider_uuid: str):
        self.settings = settings
        self.patient_uuid = patient_uuid
        self.note_uuid = note_uuid
        self.provider_uuid = provider_uuid
        self.cache = cache

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    @classmethod
    def schema_key(cls) -> str:
        raise NotImplementedError

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        raise NotImplementedError

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | _BaseCommand:
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
        # TODO use the Staff.objects.get(self.provider_uuid) to retrieve the primary location when ready
        #  for now use the first location
        if practice := PracticeLocation.objects.order_by("dbid").first():
            if setting := practice.settings.filter(name=setting).order_by("dbid").first():
                return setting.value
        return None
