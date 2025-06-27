import os
import re
import json
import argparse
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

class RubricGenerator:
    def __init__(self, llm_key: str):
        self.llm = LlmOpenai(MemoryLog.dev_null_instance(), llm_key, Constants.OPENAI_CHAT_TEXT, False)

    @staticmethod
    def load_json(path: Path):
        with path.open('r') as f:
            return json.load(f)

    def build_prompt(self, transcript, chart, canvas_context):
        self.llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical informatics expert working with a senior physician to build innovative medical education software. "
                "You specialize in designing case-specific rubrics to evaluate the quality of medical scribe notes."
            ]
        ))

        self.llm.add_prompt(LlmTurn(
            role='user',
            text=[
                "Your task is to define a quality and safety grading rubric for clinical documentation related to a partial segment of a specific patient encounter (the 'case'), based on the patient's medical background and a partial transcript of the encounter. Both the background and transcript are supplied at the end of this prompt.",
                
                "You must first read the medical background information and transcript very carefully, paying attention to all the details so that you understand, to the best of what is possible given the evidence, what the medical situation is.",
                "You must use your vast background in established clinical practice guidelines to develop the smallest comprehensive set of criteria that are mutually exclusive and collectively exhaustive of the major quality and safety criteria that characterize good medical decision making and fastidious documentation of the partial segment of the patient encounter.",
                "It is critically important that each criterion you write is maximally independent from the other criteria, and can be evaluated on its own, independent of the other criteria.",
                
                "Each criterion must assert the presence or absence of content or characteristic of the documentation, such that a grader is subsequently able to ascertain on a scale of 0% to 100% the degree to which the criterion is satisfied.", 
                "Each criterion must be formatted as the json object {\"criterion\": <clear, verifiable criterion that tests for presence or absence of positive or negative content or characteristics of the documentation>, \"weight\": <an integer weight between 0 and 100 that indicates the importance of the criterion relative to the other criteria in the rubric>, \"sense\": <\"negative\"|\"positive\">}.",
                "The rubric itself must be expressed as an array of criteria. There must be no other commentary or markdown or enclosing characters in your response, only valid json that can be directly processed by a downstream computer program.",
                
                "Each criterion must start with either \"Penalize for\" or \"Reward for\".",
                "Each criterion must start with \"Penalize for\" and have a \"negative\" sense if the criterion tests for presence of bad characteristics, such as an excessively risky decision, an incorrect or inappropriate decision, an omission of key clinical or medico-legal detail, absence of clinically relevant social determinant information, excessive brevity, excessive wordiness, redundant information, etc.",
                "Each criterion must start with \"Reward for\" and have a \"positive\" sense if the criterion tests for presence of good characteristics, such as safe or appropriate-risk decisions, correct decisions, inclusion of key clinical and medico-legal detail, presence of clinically relevant social determinant information, appropriate brevity, appropriate detail, etc.",
                
                "You must consider patient safety in your development of the rubric, and as a result there must be at least one criterion addressing patient safety, in whatever way is appropriate for the case.",
                "You must consider clinical best practice guidelines in your development of the rubric, and as a result there must be at least one criterion addressing evidence-based decision making in whatever way is appropriate for the case.",
                
                "You must keep the number of criteria as small as possible while covering all of the essential angles, an important balancing act.",
                "You must make the criteria as specific as possible to the exact case, and completely avoid broad generalizations that cannot be directly and literally tested against the same case transcript and medical background information you have here as context for developing the rubric.",
                
                "**Be extremely strict about preventing redundancy or unnecessary repetition. Notes should focus only on new, relevant, case-specific information and appropriate decisions informed by, but not duplicating, the chart.**",
                
                "DO NOT include any Markdown, code block formatting, explanations, or extraneous text — only output the pure JSON array that can be loaded with json.loads().",
                
                "Your output must begin with the [ character and end with the ] character. Do not include any Markdown syntax, code block markers, or language tags such as ```json. Output the raw JSON array only, nothing else.",
                
                "Below is the data to inform your rubric design:",
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

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, output_path: Path):
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        self.build_prompt(transcript, chart, canvas_context)

        print("Generating rubric...")
        response = self.llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

        try:
            rubric = json.loads(cleaned)
            with output_path.open('w') as f:
                json.dump(rubric, f, indent=2)
            print(f"Wrote rubric to {output_path}")
        except json.JSONDecodeError:
            print("Warning: LLM response is not valid JSON. Saving raw output instead.")
            with output_path.open('w') as f:
                f.write(cleaned)
            print(f"Wrote raw response to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate a rubric JSON file from transcript, chart, and canvas context.")
    parser.add_argument("transcript_path", type=Path, help="Path to transcript.json")
    parser.add_argument("chart_path", type=Path, help="Path to limited_chart.json")
    parser.add_argument("canvas_context_path", type=Path, help="Path to canvas_context.json")
    parser.add_argument("output_path", type=Path, help="Path to save rubric.json")

    args = parser.parse_args()

    llm_key = os.environ['KeyTextLLM']
    generator = RubricGenerator(llm_key)
    generator.generate(args.transcript_path, args.chart_path, args.canvas_context_path, args.output_path)

if __name__ == "__main__":
    main()
