import os
import re
import json
import argparse
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

class RubricPrelabelGenerator:
    def __init__(self, llm_key: str):
        self.llm_key = llm_key
        self.memory_log = MemoryLog.dev_null_instance()
        self.llm = LlmOpenai(self.memory_log, self.llm_key, Constants.OPENAI_CHAT_TEXT, False)

    @staticmethod
    def load_json(path: Path):
        with path.open('r') as f:
            return json.load(f)

    @staticmethod
    def save_json(obj, path: Path):
        with path.open('w') as f:
            json.dump(obj, f, indent=2)

    def label_transcript(self, transcript, chart):
        self.llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical labeling assistant. Your job is to help with rubric development by preprocessing a medical encounter transcript into a structured set of labeled utterances.",
                "The goal is to make each speaker turn more interpretable for downstream rubric generation, especially when evaluating whether key points were reflected in the final clinical note."
            ]
        ))

        self.llm.add_prompt(LlmTurn(
            role='user',
            text=[
                "For **each turn** in the transcript, extract the speaker identity and the exact text of the turn, and assign a **summary label** (no more than five words) that captures the core intent or function of that turn.",
                "The label should help a downstream system quickly interpret what this turn was about (e.g., 'chief complaint description', 'treatment plan discussion', 'medication change request').",
                "Do NOT omit any turns — label all of them, even if the label is simple like 'small talk' or 'follow-up logistics'.",
                "Do NOT modify the original turn text. Only add the label field.",
                "Return a JSON array. Each element must be a JSON object in this format:",
                "{\"speaker\": <speaker>, \"text\": <exact text>, \"label\": <≤5-word summary of the intent>}",

                "--- BEGIN TRANSCRIPT JSON ---",
                json.dumps(transcript),
                "--- END TRANSCRIPT JSON ---",
                "--- BEGIN CHART JSON ---",
                json.dumps(chart),
                "--- END CHART JSON ---"
            ]
        ))

        print("Labeling transcript for prelabel rubric strategy...")
        response = self.llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print("Warning: LLM response is not valid JSON. Returning raw text.")
            return cleaned


    def build_prompt_from_labeled(self, labeled_transcript, chart, canvas_context):
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
                
                "You must first read the labeled transcript and chart carefully to understand the clinical context, but your rubric must only measure note accuracy and completeness relative to those sources.",
                
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
                json.dumps(labeled_transcript),
                "--- END TRANSCRIPT JSON ---",
                "--- BEGIN CHART JSON ---",
                json.dumps(chart),
                "--- END CHART JSON ---",
                "--- BEGIN CANVAS CONTEXT JSON ---",
                json.dumps(canvas_context),
                "--- END CANVAS CONTEXT JSON ---"
            ]
        ))
        print("Generating rubric based on labeled transcript...")
        response = self.llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print("Warning: LLM rubric output is not valid JSON. Returning raw text.")
            return cleaned

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, label_path: Path, rubric_output_path: Path):
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        labeled = self.label_transcript(transcript, chart)
        self.save_json(labeled, label_path)

        rubric = self.build_prompt_from_labeled(labeled, chart, canvas_context)
        self.save_json(rubric, rubric_output_path)

        print(f"Rubric written to {rubric_output_path} and labeled transcript to {label_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate rubric via transcript labeling strategy.")
    parser.add_argument("transcript_path", type=Path, help="Path to transcript.json")
    parser.add_argument("chart_path", type=Path, help="Path to limited_chart.json")
    parser.add_argument("canvas_context_path", type=Path, help="Path to canvas_context.json")
    parser.add_argument("label_output_path", type=Path, help="Path to save transcript_labeled.json")
    parser.add_argument("rubric_output_path", type=Path, help="Path to save rubric_prelabel.json")

    args = parser.parse_args()
    llm_key = os.environ['KeyTextLLM']

    generator = RubricPrelabelGenerator(llm_key)
    generator.generate(
        args.transcript_path,
        args.chart_path,
        args.canvas_context_path,
        args.label_output_path,
        args.rubric_output_path
    )

if __name__ == "__main__":
    main()
