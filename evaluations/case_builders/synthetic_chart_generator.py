import json
import uuid
from typing import Any, Dict, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.limited_cache import LimitedCache
from evaluations.case_builders.synthetic_json_helper import generate_json

class ChartGenerator:
    def __init__(self, vendor_key: VendorKey, example_chart: Dict[str, Any]) -> None:
        self.vendor_key = vendor_key
        self.example_chart = example_chart

    def _schema(self) -> Dict[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object"
        }

    def _assign_valid_uuids(self, obj: Any) -> Any:
        stack: list[Tuple[Any, Any]] = [(None, obj)]
        while stack:
            parent, current = stack.pop()
            if isinstance(current, dict):
                for k, v in current.items():
                    if k.lower() == "uuid":
                        current[k] = str(uuid.uuid4())
                    else:
                        stack.append((current, v))
            elif isinstance(current, list):
                for item in current:
                    stack.append((current, item))
        return obj

    def _validate_chart(self, chart: Dict[str, Any]) -> None:
        try:
            LimitedCache.load_from_json(chart)
        except Exception as e:
            raise ValueError(f"Invalid limited_chart structure: {e}")

    def generate_chart_for_profile(self, profile_text: str) -> Dict[str, Any]:
        system_prompt = [
            "You are generating a Canvas Medical compatible limited_chart.json "
            "for a synthetic patient.",
            "Your output must match the JSON structure provided. Do not add unrelated fields or categories.",
            "Leave any unrelated categories as empty arrays. Do not fabricate information "
            "beyond what the patient profile describes."
        ]

        user_prompt = [
            f"Patient profile: {profile_text}",
            "Here is an example structure:",
            "```json",
            json.dumps(self.example_chart, indent=2),
            "```",
            "Generate a valid limited_chart.json for this patient. "
            "Only output raw JSON — no markdown, no commentary.",
            "Be strict about including only information that is clearly **already known** in the profile.",
            "Include only conditions the patient **has had or is diagnosed with**, not symptoms or possibilities.",
            "Include only medications the patient is **actually taking**, not ones they might take.",
            "Everything in the chart must be retrospective and factual."
        ]

        chart_json = cast(Dict[str, Any], generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=self._schema(),
            retries=3))

        self._validate_chart(chart_json)
        chart = self._assign_valid_uuids(chart_json)
        return chart
