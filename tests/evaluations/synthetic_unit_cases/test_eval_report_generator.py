import csv
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


def test_script_generates_csv(tmp_path, monkeypatch):
    rubric_path, scores_path, output = _write_inputs(tmp_path, n=3)

    monkeypatch.setattr(
        sys, "argv",
        ["eval_report.py", str(rubric_path), str(scores_path), str(output)],)

    runpy.run_module(
        "evaluations.cases.synthetic_unit_cases.eval_report_generator", run_name="__main__")

    assert output.exists()
    rows = list(csv.DictReader(output.open()))
    assert len(rows) == 3
    assert rows[0]["Criterion #"] == "1"
    assert rows[0]["Max Score"] == "10"
    assert rows[0]["Satisfaction (%)"] == "95.5"
    assert rows[0]["Score Awarded"] == "9.56"


def test_length_mismatch_raises(tmp_path, monkeypatch):
    """If rubric & score lengths differ the script should raise ValueError."""
    rubric_p, scores_p, out_p = _write_inputs(tmp_path, n=2)
    scores_p.write_text(json.dumps([{"satisfaction": 80, "score": 8, "rationale": "x"}]))

    monkeypatch.setattr(sys, "argv",
        ["eval_report_generator.py", str(rubric_p), str(scores_p), str(out_p)],
    )

    with pytest.raises(ValueError):
        runpy.run_module(
            "evaluations.cases.synthetic_unit_cases.eval_report_generator", run_name="__main__")
