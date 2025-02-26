from canvas_sdk.commands.base import _BaseCommand

from commander.protocols.limited_cache import LimitedCache
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


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

    def command_from_json(self, parameters: dict) -> None | _BaseCommand:
        raise NotImplementedError

    def command_parameters(self) -> dict:
        raise NotImplementedError

    def instruction_description(self) -> str:
        raise NotImplementedError

    def instruction_constraints(self) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError
