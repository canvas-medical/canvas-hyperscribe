import os
import re
import json
import argparse
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class RubricGeneratorSelfConsistency:
    def __init__(self, llm_key: str):
        self.llm_key = llm_key
        self.llm = LlmOpenai(MemoryLog.dev_null_instance(), self.llm_key, Constants.OPENAI_CHAT_TEXT, False)

    @staticmethod
    def load_json(path: Path):
        with path.open("r") as f:
            return json.load(f)

    @staticmethod
    def save_json(data, path: Path):
        with path.open("w") as f:
            json.dump(data, f, indent=2)

    def run_single_generation(self, transcript, chart, canvas_context) -> list[dict]:
        self.llm.clear_prompts()
        self.llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical informatics expert working with a senior physician to build innovative medical education software. "
                "You specialize in designing case-specific rubrics to evaluate how faithfully a medical scribe note reflects the conversation between a clinician and patient, as recorded in a transcript, and any relevant information in the patient's chart."
            ]
        ))

        self.llm.add_prompt(LlmTurn(
            role='user',
            text=[
                "Your task is to design a grading rubric for evaluating the fidelity of a medical scribe note. "
                "Fidelity is defined as the degree to which the note reflects exactly what was said or implied in the transcript, using relevant context from the chart. "
                "Do not judge the clinical quality of decisions or actions — your role is not to evaluate what should have been done, only what was actually stated and how well that is reflected in the note.",
                
                "The scribe's job is not to correct clinical mistakes, infer intentions, or introduce new content. The rubric must reward or penalize the documentation *solely* based on whether it captured what was *explicitly or implicitly* stated in the transcript, and whether it leveraged relevant details from the chart without copying irrelevant ones.",
                "The transcript is the source of truth — even if it contains questionable decisions, you must assume they were spoken and should be documented accordingly. Do not bring in external clinical knowledge or judge decisions using best practices or safety standards. Only consider fidelity to what is said and known.",
                
                "You must first read the transcript and chart carefully to understand the clinical context, but your rubric must only measure note accuracy and completeness relative to those sources.",
                
                "Each criterion must reflect whether the note *faithfully and accurately* documents a key fact, statement, action, or detail from the transcript or chart — and must be verifiable based on these sources alone.",
                "You must write **only fidelity-based criteria**: omissions, misstatements, additions not grounded in the transcript or chart, mischaracterizations of tone, inaccuracy in names/times/dosages/etc., or failure to capture relevant medical background information.",
                
                "Do not include any clinical quality judgments such as 'was it a good plan?' or 'should the medication have been prescribed?' — only whether it was *said* and was *documented faithfully*.",
                
                "Each criterion must be formatted as a JSON object: {\"criterion\": <clear, verifiable fidelity-focused criterion>, \"weight\": <int from 0–100>, \"sense\": \"positive\"|\"negative\"}.",
                "Each must start with either 'Reward for' (high-fidelity inclusion) or 'Penalize for' (low-fidelity omission, distortion, or fabrication).",
                
                "You must include at least one criterion that addresses overall completeness of note relative to transcript, and at least one that addresses selective or inaccurate copying from the chart.",
                
                "Avoid any criteria that require judgment beyond what can be verified directly in the transcript or chart. Be strict about this.",
                "Keep the number of criteria minimal but sufficient to cover fidelity from multiple angles (verbatim match, selective copying, structural fidelity, contextual misrepresentation, etc.).",
                
                "Only return a JSON array of criteria. No commentary, markdown, or text wrapping. Your output must start with [ and end with ].",
                
                "--- BEGIN TRANSCRIPT JSON ---",
                json.dumps(transcript),
                "--- END TRANSCRIPT JSON ---",
                "--- BEGIN CHART JSON ---",
                json.dumps(chart),
                "--- END CHART JSON ---",
                "--- BEGIN CANVAS CONTEXT JSON ---",
                json.dumps(canvas_context),
                "--- END CANVAS CONTEXT JSON ---"
            ]
        ))

        print("Generating a rubric draft...")
        response = self.llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print("Warning: Failed to parse rubric JSON. Returning raw text.")
            return cleaned

    def run_consistency_generation(self, rubric_1, rubric_2, rubric_3, transcript, chart, canvas_context):
        self.llm.clear_prompts()

        self.llm.set_system_prompt([
            "You are a clinical informatics expert analyzing multiple drafts of rubrics that evaluate documentation fidelity. "
            "You are responsible for resolving inconsistencies and synthesizing a final consistent rubric."
        ])

        self.llm.set_user_prompt([
            "Below are three rubric drafts. Your job is to carefully compare and synthesize them into a final, internally consistent rubric "
            "that maximally reflects fidelity — i.e., whether the scribe note reflects what was said and implied in the transcript given chart context.",

            "The final rubric should:",
            "- Remove redundancies",
            "- Resolve contradictions",
            "- Keep high-signal criteria from each draft",
            "- Preserve mutual exclusivity and coverage of fidelity-relevant dimensions",
            "- Follow the fidelity-focused JSON rubric structure",

            "Format each criterion as: "
            "{\"criterion\": ..., \"weight\": ..., \"sense\": \"positive\"|\"negative\"}. Begin each with 'Reward for ...' or 'Penalize for ...'.",
            "Return a single valid JSON array only. No markdown, no extra commentary.",

            "--- BEGIN RUBRIC DRAFT 1 ---",
            json.dumps(rubric_1),
            "--- END RUBRIC DRAFT 1 ---",
            "--- BEGIN RUBRIC DRAFT 2 ---",
            json.dumps(rubric_2),
            "--- END RUBRIC DRAFT 2 ---",
            "--- BEGIN RUBRIC DRAFT 3 ---",
            json.dumps(rubric_3),
            "--- END RUBRIC DRAFT 3 ---",
            "--- BEGIN TRANSCRIPT JSON ---",
            json.dumps(transcript),
            "--- END TRANSCRIPT JSON ---",
            "--- BEGIN CHART JSON ---",
            json.dumps(chart),
            "--- END CHART JSON ---",
            "--- BEGIN CANVAS CONTEXT JSON ---",
            json.dumps(canvas_context),
            "--- END CANVAS CONTEXT JSON ---"
        ])

        print("Synthesizing consistent rubric from 3 drafts...")
        response = self.llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print("Warning: Final consistency output not valid JSON.")
            return cleaned

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, output_dir: Path):
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        rubric_1 = self.run_single_generation(transcript, chart, canvas_context)
        rubric_2 = self.run_single_generation(transcript, chart, canvas_context)
        rubric_3 = self.run_single_generation(transcript, chart, canvas_context)

        self.save_json(rubric_1, output_dir / "rubric_rep1.json")
        self.save_json(rubric_2, output_dir / "rubric_rep2.json")
        self.save_json(rubric_3, output_dir / "rubric_rep3.json")

        final_rubric = self.run_consistency_generation(rubric_1, rubric_2, rubric_3, transcript, chart, canvas_context)
        self.save_json(final_rubric, output_dir / "rubric_consistent.json")


def main():
    parser = argparse.ArgumentParser(description="Generate multiple rubric drafts and synthesize a consistent one.")
    parser.add_argument("transcript_path", type=Path)
    parser.add_argument("chart_path", type=Path)
    parser.add_argument("canvas_context_path", type=Path)
    parser.add_argument("output_dir", type=Path)

    args = parser.parse_args()

    llm_key = os.environ["KeyTextLLM"]
    generator = RubricGeneratorSelfConsistency(llm_key)
    generator.generate(args.transcript_path, args.chart_path, args.canvas_context_path, args.output_dir)


if __name__ == "__main__":
    main()
