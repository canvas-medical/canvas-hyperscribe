from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Type
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.line import Line
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.chart import Chart
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.structures.graded_criterion import GradedCriterion
from evaluations.structures.clause_verdict import ClauseVerdict
from hyperscribe.structures.model_spec import ModelSpec


class HelperSyntheticJson:
    @staticmethod
    def generate_json(
        system_prompt: list[str],
        user_prompt: list[str],
        schema: dict[str, Any],
        returned_class: Type[Chart | Line | PatientProfile | RubricCriterion | GradedCriterion | ClauseVerdict],
        model: str | None = None,
        anthropic_4_7_compat: bool = False,
    ) -> (
        Chart | list[Line] | list[PatientProfile] | list[RubricCriterion] | list[GradedCriterion] | list[ClauseVerdict]
    ):
        """
        1) Creates a LLM client.
        2) Sends *system_prompt* and *user_prompt* (lists of strings).
        3) Extracts the JSON payload from a fenced block or raw output.
        4) Validates the payload against *schema* with jsonschema.
        5) On validation failure, writes the raw output to invalid_output.json
           and exits with status 1.

        ``model`` overrides the model that ``Helper.chatter`` resolves from
        ``Constants``. Vendor dispatch still comes from the settings, so only the model
        name changes. Callers use this when the default is wrong for their task: the
        exam-merge judge, for instance, must not grade with the same model that produced
        the output it is grading.

        ``anthropic_4_7_compat`` adapts the request for Anthropic models from the 4.7
        generation onward, which ``LlmAnthropic`` cannot otherwise talk to at all. Two
        incompatibilities, both in the plugin's client:

        * it always emits ``temperature``, which those models reject outright (HTTP 400);
        * it reads the response as ``content[0]["text"]``, but those models put a
          ``thinking`` block at index 0, so the client sees an empty string and burns its
          retries.

        Setting ``thinking`` to disabled collapses the response to a single text block,
        which the existing parser handles. The cost is that the judge runs without
        extended thinking. Confined to this eval layer on purpose: fixing the plugin's
        client is the real answer, but that client is shared by every legacy command and
        is already deployed.
        """
        settings = HelperEvaluation.settings_reasoning_allowed()
        llm = Helper.chatter(settings, MemoryLog.dev_null_instance(), ModelSpec.COMPLEX)
        if model:
            llm.model = model
        if anthropic_4_7_compat:
            HelperSyntheticJson._apply_anthropic_4_7_compat(llm)

        llm.set_system_prompt(system_prompt)
        llm.set_user_prompt(user_prompt)

        result = llm.chat(schemas=[schema])

        if result.has_error:
            Path("invalid_output.json").write_text(result.error)
            print("LlmBase.chat() returned an error; error message saved to invalid_output.json")
            sys.exit(1)

        parsed = result.content[0]

        if returned_class in [Chart, Line, PatientProfile, RubricCriterion, GradedCriterion, ClauseVerdict]:
            return returned_class.load_from_json(parsed)

        raise ValueError(f"Unsupported returned_class: {returned_class}")

    @staticmethod
    def _apply_anthropic_4_7_compat(llm: Any) -> None:
        """Drop ``temperature`` and disable thinking on this one client instance.

        Rebinds ``to_dict`` on the instance rather than editing the client class, so the
        change cannot reach the shipped plugin.
        """
        original = llm.to_dict

        def adjusted() -> dict[str, Any]:
            payload: dict[str, Any] = dict(original())
            payload.pop("temperature", None)
            payload["thinking"] = {"type": "disabled"}
            return payload

        llm.to_dict = adjusted
