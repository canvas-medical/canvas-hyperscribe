import sys, os, json, argparse, re
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


def load_json(path):
    with open(path) as f:
        return json.load(f)


def main(rubric_path, note_path, output_path):
    rubric = load_json(rubric_path)
    note = load_json(note_path)

    llm = LlmOpenai(
        MemoryLog.dev_null_instance(),
        os.environ["KeyTextLLM"],
        Constants.OPENAI_CHAT_TEXT,
        False
    )

    llm.add_prompt(LlmTurn(role="system", text=[
        "You are a clinical documentation grading assistant. You help evaluate medical scribe notes using structured rubrics."
    ]))

    llm.add_prompt(LlmTurn(role="user", text=[
        ("Given the rubric and the hyperscribe output below, return a JSON array where each item corresponds to one rubric criterion, "
                "in the same order as the rubric. Each item must be a dictionary with the following keys:\n"
                "- 'rationale': a short, specific explanation of how well the criterion was satisfied or not.\n"
                "- 'satisfaction': a numeric value between 0 and 100 (can be any float such as 20, 55, or 85, not just 0, 50, 100),"
                "indicating how well the criterion was satisfied.\n"),
        ("Maintain the original order and structure of the rubric—output must be a list of the same length and order as the rubric input."),
        ("Output ONLY the raw JSON array, starting with [ and ending with ]. No markdown, no extra text, no explanation."),
        "--- BEGIN RUBRIC JSON ---",
            json.dumps(rubric),
            "--- END RUBRIC JSON",
            "--- BEGIN HYPERSCRIBE OUTPUT JSON ---",
            json.dumps(note),
            "--- END HYPERSCRIBE OUTPUT JSON ---",
    ]))
    print("Grading …")
    raw = llm.request().response
    cleaned = re.sub(r"```(?:json)?\n?|\n?```", "", raw).strip()

    try:
        llm_results = json.loads(cleaned)
    except json.JSONDecodeError:
        print("LLM produced invalid JSON — saving raw and exiting.")
        Path(output_path).write_text(cleaned)
        sys.exit(1)

    final = []
    for criteria, result in zip(rubric, llm_results):
        sat = float(result["satisfaction"])
        weight = criteria["weight"]
        if criteria["sense"] == "positive":
            score = round(weight * (sat / 100), 2)
        else:
            score = -1 * round(weight * (1 - (sat / 100)), 2)
        final.append({
            "rationale": result["rationale"],
            "satisfaction": sat,
            "score": score
        })

    with open(output_path, "w") as f:
        json.dump(final, f, indent=2)
    print("Saved grading result →", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("rubric_path")
    parser.add_argument("hyperscribe_output_path")
    parser.add_argument("output_path")
    args = parser.parse_args()
    main(args.rubric_path, args.hyperscribe_output_path, args.output_path)