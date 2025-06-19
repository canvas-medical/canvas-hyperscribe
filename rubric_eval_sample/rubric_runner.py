import os
import subprocess

def run_rubric(case_name: str, transcript_path: str, rubric_path: str) -> None: 
    #started out in root directory.
    project_root = os.path.dirname(os.path.abspath(__file__))  # rubric_eval_sample/
    project_root = os.path.abspath(os.path.join(project_root, ".."))  # canvas-hyperscribe/

    chart_path = os.path.join(project_root, "evaluations", "datastores", "cases","limited_caches", f"{case_name}.json")
    canvas_context_path = os.path.join(project_root,"rubric_eval_sample","canvas_context.json")

    for path in [transcript_path, chart_path, canvas_context_path]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Required file not found: {path}")

    subprocess.run(["uv", "run", "env", f"PYTHONPATH={project_root}","python", os.path.join("rubric_eval_sample", "rubric.py"), 
                    transcript_path, chart_path, canvas_context_path, rubric_path], check=True)
