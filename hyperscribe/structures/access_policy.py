from __future__ import annotations

from typing import NamedTuple


class AccessPolicy(NamedTuple):
    policy: bool  # define if the listed items are allowed or excluded (default)
    items: list[str]

    def is_allowed(self, item: str) -> bool:
        return (item in self.items) is self.policy

    @classmethod
    def allow_all(cls) -> AccessPolicy:
        return AccessPolicy(policy=False, items=[])
