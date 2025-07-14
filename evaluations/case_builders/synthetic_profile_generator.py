import json
from typing import Any, Dict, List, Tuple, cast
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.synthetic_json_helper import generate_json

class PatientProfileGenerator:
    def __init__(self, vendor_key: VendorKey) -> None:
        self.vendor_key = vendor_key
        self.seen_scenarios: List[str] = []

    def _summarize(self, narrative: str) -> str:
        return narrative.split(".")[0][:100]

    def _schema(self, count: int) -> Dict[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "minProperties": count,
            "maxProperties": count,
            "patternProperties": {r"^Patient\s\d+$": {"type": "string"}},
            "additionalProperties": False,
        }

    def generate_batch(self, batch_num: int, count: int) -> List[Tuple[str, str]]:
        schema = self._schema(count)

        system_prompt = [
            "You are a clinical informatics expert generating synthetic patient profiles "
            "for testing medication management AI systems. Format your response strictly "
            "according to this JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
        ]

        user_prompt = [
            f"Create a JSON object with {count} key-value pairs labeled "
            f"\"Patient {1 + (batch_num-1)*count}\" through \"Patient {batch_num*count}\". "
            "Each value must be a 3-to-5-sentence medication-history narrative "
            "written for a broad audience (≈ 40-60 plain-English words).",
            "",
            "Include **at least two** LOW-complexity patients "
            "(single renewal, first-time Rx, or simple dose tweak). Other patients may be moderate "
            "or high complexity, guided by the diversity checklist below:",
            "- Age bands: <18, 18-30, 30-50, 50-70, >70.",
            "- Social context: homelessness, language barrier, uninsured, rural isolation, etc.",
            "- Novel drug classes: GLP-1 agonists, oral TKIs, depot antipsychotics, inhaled steroids, biologics, antivirals, contraception, chemo, herbals.",
            "- Edge-case themes: pregnancy, QT risk, REMS, dialysis, polypharmacy/deprescribing, travel medicine, etc.",
            "",
            f"Already-seen motifs → {', '.join(self.seen_scenarios) if self.seen_scenarios else 'None yet'}. "
            "**Avoid** re-using templates like ACE-inhibitor-to-ARB cough, long-term warfarin INR drift, or COPD tiotropium boilerplate.",
            "",
            "Write in clear prose with minimal jargon. If a medical abbreviation is unavoidable, "
            "spell it out the first time (e.g., “twice-daily (BID)”). Prefer full words: “by mouth” "
            "over “PO”, “under the skin” over “SC”. Vary openings: lead with social detail, "
            "medication list, or family history.",
            "",
            "Each narrative MUST include:",
            "• Current medicines in plain words, with some cases not having complete details.",
            "• A scenario involving medication management—straightforward new prescriptions, simple dose adjustments, or complex edge cases involving risky medications, polypharmacy, or social barriers.",
            "• Any key allergy, condition, or social barrier.",
            "",
            "Do NOT write SOAP notes, vital signs, or assessments.",
            "Return **raw JSON only** – no markdown, headings, or commentary."
        ]

        batch = cast(Dict[str, str], generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            retries=3,))

        results: List[Tuple[str, str]] = []
        for name, narrative in batch.items():
            self.seen_scenarios.append(self._summarize(narrative))
            results.append((name, narrative))
        return results

    def generate_profiles(self, batches: int, size: int) -> List[Tuple[str, str]]:
        all_profiles: List[Tuple[str, str]] = []
        for i in range(1, batches + 1):
            print(f"Generating batch {i}…")
            all_profiles.extend(self.generate_batch(i, size))
            
        return all_profiles
