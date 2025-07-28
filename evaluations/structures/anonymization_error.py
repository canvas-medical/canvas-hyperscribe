from typing import NamedTuple


class AnonymizationError(NamedTuple):
    has_errors: bool
    errors: list[str]
