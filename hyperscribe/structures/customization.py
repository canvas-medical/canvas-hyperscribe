from __future__ import annotations

from typing import NamedTuple

from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.default_tab import DefaultTab


class Customization(NamedTuple):
    custom_prompts: list[CustomPrompt]
    ui_default_tab: DefaultTab

    @classmethod
    def load_from_json(cls, data: dict) -> Customization:
        return Customization(
            custom_prompts=CustomPrompt.load_from_json_list(data["customPrompts"]),
            ui_default_tab=DefaultTab(data["uiDefaultTab"]),
        )

    def to_dict(self) -> dict:
        return {
            "customPrompts": [prompt.to_json() for prompt in self.custom_prompts],
            "uiDefaultTab": self.ui_default_tab.value,
        }
