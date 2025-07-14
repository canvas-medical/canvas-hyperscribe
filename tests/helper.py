from __future__ import annotations

from dataclasses import fields as dataclass_fields, is_dataclass as dataclass_is_dataclass
from re import sub
from typing import get_type_hints


def is_namedtuple(cls, fields: dict) -> bool:
    return (
            issubclass(cls, tuple)
            and hasattr(cls, '_fields')
            and isinstance(cls._fields, tuple)
            and len([field for field in cls._fields if field in fields]) == len(fields.keys())
            and get_type_hints(cls) == fields
    )


def is_dataclass(cls, fields: dict) -> bool:
    return (
            dataclass_is_dataclass(cls)
            and len([field for field in dataclass_fields(cls) if field.name in fields]) == len(fields.keys())
            and all(fields[field.name] == field.type for field in dataclass_fields(cls))
    )


def is_constant(cls, constants: dict) -> bool:
    count = len([
        attr
        for attr in dir(cls)
        if attr.upper() == attr and not (attr.startswith("_") or callable(getattr(cls, attr)))])
    if count != len(constants.keys()):
        print(f"----> counts: {count} != {len(constants.keys())}")
        return False

    for key, value in constants.items():
        if getattr(cls, key) != value:
            print(f"----> {key} value is {getattr(cls, key)}")
            return False
    return True


def compare_sql(left: str, right: str) -> bool:
    cleaned_left = sub(r"\s+", " ", left).strip()
    cleaned_right = sub(r"\s+", " ", right).strip()
    if cleaned_left == cleaned_right:
        return True
    assert cleaned_left == cleaned_right, f">{cleaned_left}<"
    return False

class MockFile:

    def __init__(self, content: str | bytes = "", mode: str = ""):
        self.content = content
        self.mode = mode

    def read(self):
        return self.content

    def write(self, text: str | bytes):
        self.content = self.content + text
        return len(text)

    def close(self):
        ...

    def __enter__(self):
        if "w" in self.mode and "+" not in self.mode:
            self.content = b"" if "b" in self.mode else ""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
