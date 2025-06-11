from __future__ import annotations

from typing import NamedTuple


class CommandsPolicy(NamedTuple):
    policy: bool  # define if the listed commands are allowed or excluded (default)
    commands: list[str]

    def is_allowed(self, class_name: str) -> bool:
        return (class_name in self.commands) is self.policy

    @classmethod
    def allow_all(cls) -> CommandsPolicy:
        return CommandsPolicy(policy=False, commands=[])
