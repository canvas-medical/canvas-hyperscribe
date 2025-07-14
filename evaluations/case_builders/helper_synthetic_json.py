import re, json, sys, jsonschema
from pathlib import Path
from typing import Any, Dict, List
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.http_response import HttpResponse

class HelperSyntheticJson:
    def generate_json(vendor_key: VendorKey, system_prompt: List[str], user_prompt: List[str],
        schema: Dict[str, Any], retries: int = 3) -> Any:
        """
        1) Starts on the O3 client
        2) Sends system + user prompts
        3) Schema validation
        4) If error, concat last output and error into prompts and retry
        5) After retries failures, saves the last raw JSON to invalid_output.json and exits
        """
        llm = LlmOpenaiO3(
            MemoryLog.dev_null_instance(),
            vendor_key.api_key,
            with_audit=False)

        initial_system = system_prompt.copy()
        initial_user   = user_prompt.copy()
        error_prompt: List[str] = []
        last_clean = ""

        for attempt in range(retries):
            if attempt == 0:
                llm.set_system_prompt(initial_system)
                llm.set_user_prompt(initial_user)
            else:
                combined_user = (
                    initial_user
                    + ["--- Previous assistant output ---"]
                    + response.response.splitlines()
                    + error_prompt
                )
                llm.set_system_prompt(initial_system)
                llm.set_user_prompt(combined_user)

            response: HttpResponse = llm.request()
            raw = response.response
            cleaned  = re.sub(r'```(?:json)?\n?|\n?```', '', raw).strip()
            last_clean = cleaned
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as e:
                error_prompt = [
                    "Your previous response has the following errors:",
                    "```text",
                    str(e),
                    "```",
                    "",
                    "Please, correct your answer following rigorously "
                    "the initial request and the mandatory response format."
                ]
                continue
            try:
                jsonschema.validate(parsed, schema)
                return parsed
            except jsonschema.ValidationError as e:
                error_prompt = [
                    "Your previous response has the following errors:",
                    "```text",
                    str(e),
                    "```",
                    "",
                    "Please, correct your answer following rigorously the initial request "
                    "and the mandatory response format."
                ]
                continue

        #if we've reached here, we just need to exit and write the text.
        error_file = Path("invalid_output.json")
        error_file.write_text(last_clean)
        print(f"Failed to generate valid JSON after {retries} attempts. "
            f"Saved invalid JSON to {error_file}")
        sys.exit(1)
