from datetime import datetime, date
from enum import Enum
from re import match
from typing import Type


class Helper:

    @classmethod
    def str2datetime(cls, string: str | None) -> datetime | None:
        try:
            return datetime.strptime(string, "%Y-%m-%d")
        except Exception:
            return None

    @classmethod
    def str2date(cls, string: str | None) -> date | None:
        if result := cls.str2datetime(string):
            return result.date()
        return None

    @classmethod
    def enum_or_none(cls, value: str, enum: Type[Enum]) -> Enum | None:
        if value in (item.value for item in enum):
            return enum(value)
        return None

    @classmethod
    def icd10_add_dot(cls, code: str) -> str:
        if result := match(r"([A-Za-z]+\d{2})(\d+)", code):
            return f"{result.group(1)}.{result.group(2)}"
        return code

    @classmethod
    def icd10_strip_dot(cls, code: str) -> str:
        return code.replace(".", "")
