import re, json, sys, jsonschema
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.vendor_key import VendorKey

class HelperSyntheticJson:
    _FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """
        If *text* contains a fenced ```json … ``` block, return its contents;
        otherwise return *text* unchanged.
        """
        match = HelperSyntheticJson._FENCE_RE.search(text)
        return (match.group(1) if match else text).strip()

    @staticmethod
    def generate_json(vendor_key: VendorKey, system_prompt: List[str],
        user_prompt: List[str], schema: Dict[str, Any],) -> Any:
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

        result = llm.chat()

        #check lower-level issues.
        if result.has_error:
            error_file = Path("invalid_output.json")
            error_file.write_text(result.error)
            print("LlmBase.chat() returned an error; raw message saved to", error_file)
            sys.exit(1)

        #extract JSON from fenced block if present, otherwise exit in error file.
        json_text = HelperSyntheticJson._extract_json_block(result.content)

        try:
            parsed = json.loads(json_text)
            jsonschema.validate(instance=parsed, schema=schema)
            return parsed

        except Exception as e:
            error_file = Path("invalid_output.json")
            error_file.write_text(result.content)
            print("Generated output failed JSON‑schema validation (", e, ").")
            print("Saved invalid output to", error_file)
            sys.exit(1)
