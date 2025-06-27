import os
import re
import json
import argparse
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

class RubricRAGGenerator:
    def __init__(self, llm_key: str):
        self.llm_key = llm_key
        self.llm = LlmOpenai(MemoryLog.dev_null_instance(), llm_key, Constants.OPENAI_CHAT_TEXT, False)

    @staticmethod
    def load_json(path: Path):
        with path.open('r') as f:
            return json.load(f)

    def build_initial_prompt(self, transcript, chart, canvas_context):
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

    def build_verification_prompt(self, criteria, transcript, chart):
        self.llm.clear_prompts()
        self.llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical rubric verification agent responsible for quality control of fidelity-based rubrics. "
                "Your job is to verify whether each rubric criterion is logically grounded, verifiable, and strictly tied to the evidence "
                "in the provided transcript of a clinical encounter and a patient chart summary. "
                "You must be extremely strict in disqualifying vague, unverifiable, or clinically assumptive criteria."
            ]
        ))

        self.llm.add_prompt(LlmTurn(
            role='user',
            text=[
                "The following list of rubric criteria was generated by a language model based on a patient's chart and a partial transcript "
                "from a clinical encounter. The rubric is intended to evaluate a medical scribe's documentation quality, strictly focusing on fidelity — "
                "how accurately the note reflects the source transcript and known chart information. The rubric must NOT reward or penalize "
                "clinical decisions themselves — only whether the documentation is complete, faithful, and relevant to the inputs provided.",
                
                "Your task is to carefully review **each criterion** and determine whether it meets the following standards:\n",
                "- It refers only to information explicitly stated or strongly implied in the transcript or chart.\n"
                "- It is specific, measurable, and unambiguous.\n"
                "- It does NOT require external clinical judgment, outside knowledge, or assumptions.\n"
                "- It does NOT judge the quality of clinical decisions (only their documentation).\n",

                "Classify each criterion as either valid or rejected.\n\n"
                "Return a **JSON object** with two keys:\n"
                "- \"valid_criteria\": a list of criteria JSON objects that meet the above fidelity standards.\n"
                "- \"rejected_criteria\": a list of any that fail for vagueness, unverifiability, redundancy, judgment of decisions, or hallucinated content.\n\n"
                "For each rejected criterion, include a brief reason in the field `rejection_reason` as part of its object.\n",

                "--- BEGIN CRITERIA JSON ---",
                json.dumps(criteria),
                "--- END CRITERIA JSON ---",
                "--- BEGIN TRANSCRIPT JSON ---",
                json.dumps(transcript),
                "--- END TRANSCRIPT JSON ---",
                "--- BEGIN CHART JSON ---",
                json.dumps(chart),
                "--- END CHART JSON ---"
            ]
        ))

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, output_path: Path):
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        self.build_initial_prompt(transcript, chart, canvas_context)
        print("Generating draft rubric...")
        draft_response = self.llm.request()
        draft_cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', draft_response.response).strip()
        try:
            criteria = json.loads(draft_cleaned)
        except json.JSONDecodeError:
            print("Failed to decode rubric draft. Writing raw output.")
            with output_path.open('w') as f:
                f.write(draft_cleaned)
            return

        self.build_verification_prompt(criteria, transcript, chart)
        print("Verifying criteria against transcript/chart...")
        verification_response = self.llm.request()
        verification_cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', verification_response.response).strip()
        try:
            verification_result = json.loads(verification_cleaned)
            valid_criteria = verification_result.get("valid_criteria", [])
        except json.JSONDecodeError:
            print("Verification step failed to decode. Saving original draft rubric.")
            valid_criteria = criteria

        # Step 3: Save final rubric
        with output_path.open('w') as f:
            json.dump(valid_criteria, f, indent=2)
        print(f"Wrote verified rubric to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate a rubric JSON file using RAG-style verification.")
    parser.add_argument("transcript_path", type=Path, help="Path to transcript.json")
    parser.add_argument("chart_path", type=Path, help="Path to limited_chart.json")
    parser.add_argument("canvas_context_path", type=Path, help="Path to canvas_context.json")
    parser.add_argument("output_path", type=Path, help="Path to save rubric.json")

    args = parser.parse_args()

    llm_key = os.environ['KeyTextLLM']
    generator = RubricRAGGenerator(llm_key)
    generator.generate(args.transcript_path, args.chart_path, args.canvas_context_path, args.output_path)

if __name__ == "__main__":
    main()