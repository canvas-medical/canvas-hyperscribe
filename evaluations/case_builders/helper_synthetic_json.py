from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.vendor_key import VendorKey

class HelperSyntheticJson:
    @staticmethod
    def generate_json(vendor_key: VendorKey, system_prompt: list[str],
        user_prompt: list[str], schema: dict[str, Any],) -> Any:
        """
        1) Creates an O3 LLM client.
        2) Sends *system_prompt* and *user_prompt* (lists of strings).
        3) Extracts the JSON payload from a fenced block or raw output.
        4) Validates the payload against *schema* with jsonschema.
        5) On validation failure, writes the raw output to invalid_output.json
           and exits with status 1.
        """
        llm = LlmOpenaiO3(MemoryLog.dev_null_instance(), vendor_key.api_key,
            with_audit=False, temperature=1.0)

        llm.set_system_prompt(system_prompt)
        llm.set_user_prompt(user_prompt)

        result = llm.chat(schemas=[schema])

        if result.has_error:
            Path("invalid_output.json").write_text(result.error)
            print("LlmBase.chat() returned an error; error message saved to invalid_output.json")
            sys.exit(1)

        parsed = result.content[0]
        return parsed