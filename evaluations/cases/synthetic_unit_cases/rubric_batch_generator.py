import os
import subprocess
import argparse

def generate_rubrics(case_path, canvas_context_path, rubric_script_path):
    transcript_path = os.path.join(case_path, "transcript.json")
    charts_dir = os.path.join(case_path, "charts")
    rubrics_dir = os.path.join(case_path, "rubrics")
    os.makedirs(rubrics_dir, exist_ok=True)

    for i in range(1, 6):
        chart_path = os.path.join(charts_dir, f"chart{i}.json")
        rubric_output_path = os.path.join(rubrics_dir, f"rubric{i}.json")

        if not os.path.exists(chart_path):
            print(f"Chart file missing: {chart_path}")
            continue

        print(f"Generating rubric for {chart_path}...")

        cmd = [
            "uv", "run", "python",
            rubric_script_path,
            transcript_path,
            chart_path,
            canvas_context_path,
            rubric_output_path
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"Saved rubric to: {rubric_output_path}")
        except subprocess.CalledProcessError:
            print(f"Error generating rubric for {chart_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case_path",
        default=os.path.expanduser("~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management/case0"),
        help="Path to the case0 directory"
    )
    parser.add_argument(
        "--canvas_context_path",
        default=os.path.expanduser("~/canvas-hyperscribe/rubric_eval_sample/canvas_context.json"),
        help="Path to canvas_context.json"
    )
    parser.add_argument(
        "--rubric_script_path",
        default=os.path.expanduser("~/canvas-hyperscribe/rubric_eval_sample/rubric.py"),
        help="Path to rubric.py"
    )
    args = parser.parse_args()

    generate_rubrics(args.case_path, args.canvas_context_path, args.rubric_script_path)
