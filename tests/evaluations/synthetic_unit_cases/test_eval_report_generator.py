import subprocess
import json
import runpy
import sys
from pathlib import Path
import pytest
from evaluations.cases.synthetic_unit_cases import eval_report_generator as erg

def _write_inputs(tmp_dir: Path, n: int = 2):
    """Return (rubric_path, scores_path, out_csv_path) with n rows each."""
    rubric = [{"criterion": f"C{i}", "weight": 10} for i in range(n)]
    scores = [
        {"satisfaction": 95.55, "score": 9.56, "rationale": "ok"} for _ in range(n)
    ]

    rubric_path = tmp_dir / "rubric.json"
    scores_path = tmp_dir / "scores.json"
    output = tmp_dir / "out.csv"

    rubric_path.write_text(json.dumps(rubric))
    scores_path.write_text(json.dumps(scores))
    return rubric_path, scores_path, output


def test_load_json_reads_file(tmp_path):
    payload = {"a": 1}
    p = tmp_path / "x.json"
    p.write_text(json.dumps(payload))
    assert erg.load_json(p) == payload


def test_script_generates_csv(tmp_path):
    rubric_path, scores_path, output_path = _write_inputs(tmp_path, n=2)
    script_path = Path("evaluations/cases/synthetic_unit_cases/eval_report_generator.py")

    result = subprocess.run(
        [
            "python", str(script_path),
            "--rubric", str(rubric_path),
            "--scores", str(scores_path),
            "--out", str(output_path)
        ],
        capture_output=True,
        text=True,
        check=False
    )

    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert output_path.exists(), "CSV file was not generated"
    content = output_path.read_text()
    assert "Criterion #" in content
    assert "Score Awarded" in content


def test_length_mismatch_raises(tmp_path):
    rubric_path, scores_path, output_path = _write_inputs(tmp_path, n=3)
    rubric_path.write_text(json.dumps([{"criterion": "C0", "weight": 10}]))

    script_path = Path("evaluations/cases/synthetic_unit_cases/eval_report_generator.py")

    result = subprocess.run(
        [
            "python", str(script_path),
            "--rubric", str(rubric_path),
            "--scores", str(scores_path),
            "--out", str(output_path)
        ],
        capture_output=True,
        text=True,
        check=False
    )

    assert result.returncode != 0, "Expected non-zero return code for mismatched lengths"
    assert "Rubric and score arrays must have the same length." in result.stderr
