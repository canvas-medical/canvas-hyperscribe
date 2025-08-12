from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Type
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.line import Line
from evaluations.constants import Constants
from evaluations.structures.chart import Chart
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.structures.graded_criterion import GradedCriterion


class HelperSyntheticJson:
    @staticmethod
    def generate_json(
        vendor_key: VendorKey,
        system_prompt: list[str],
        user_prompt: list[str],
        schema: dict[str, Any],
        returned_class: Type[Chart | Line | PatientProfile | RubricCriterion | GradedCriterion],
    ) -> Chart | list[Line] | list[PatientProfile] | list[RubricCriterion] | list[GradedCriterion]:
        """
        1) Creates an O3 LLM client.
        2) Sends *system_prompt* and *user_prompt* (lists of strings).
        3) Extracts the JSON payload from a fenced block or raw output.
        4) Validates the payload against *schema* with jsonschema.
        5) On validation failure, writes the raw output to invalid_output.json
           and exits with status 1.
        """
        llm = LlmOpenaiO3(
            MemoryLog.dev_null_instance(), vendor_key.api_key, with_audit=False, temperature=Constants.O3_TEMPERATURE
        )

        llm.set_system_prompt(system_prompt)
        llm.set_user_prompt(user_prompt)

        result = llm.chat(schemas=[schema])

        if result.has_error:
            Path("invalid_output.json").write_text(result.error)
            print("LlmBase.chat() returned an error; error message saved to invalid_output.json")
            sys.exit(1)

        parsed = result.content[0]

        if returned_class in [Chart, Line, PatientProfile, RubricCriterion, GradedCriterion]:
            return returned_class.load_from_json(parsed)

        raise ValueError(f"Unsupported returned_class: {returned_class}")
