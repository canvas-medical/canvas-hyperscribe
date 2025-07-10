import json, sys, csv, pytest
from pathlib import Path
from evaluations.case_builders.grader_report_generator import EvalReportGenerator

def _write_json(tmp_path: Path, data, filename: str) -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps(data))
    return path

def test_load_json_reads_list_of_dicts(tmp_path):
    tested = EvalReportGenerator
    expected = [{"foo": 123}, {"bar": 456}]
    path = _write_json(tmp_path, expected, "test.json")
    result = tested.load_json(path)
    assert result == expected

def test_run_writes_csv_with_proper_rounding(tmp_path, capsys, monkeypatch):
    tested = EvalReportGenerator
    rubric = [
        {"criterion": "First",  "weight": 3},
        {"criterion": "Second", "weight": 7},]
    scores = [
        {"satisfaction": 0.166,  "score": 1.239,   "rationale": "A"},
        {"satisfaction": 99.96,  "score": 2.71828, "rationale": "B"},]

    rubric_path = _write_json(tmp_path, rubric, "rubric.json")
    scores_path = _write_json(tmp_path, scores, "scores.json")
    out_csv     = tmp_path / "report.csv"

    #argv for run()
    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--rubric", str(rubric_path),
        "--scores", str(scores_path),
        "--out",    str(out_csv),
    ])
    tested.run()

    assert out_csv.exists()
    with out_csv.open() as f:
        result = list(csv.DictReader(f))

    expected_keys = {
        "Criterion #",
        "Criterion",
        "Max Score",
        "Satisfaction (%)",
        "Score Awarded",
        "Rationale",
    }
    assert set(result[0].keys()) == expected_keys

    expected_r1 = {
        "Criterion #": "1",
        "Criterion": "First",
        "Max Score": "3",
        "Satisfaction (%)": "0.2",
        "Score Awarded": "1.24",
        "Rationale": "A",}
    assert result[0] == expected_r1

    expected_r2 = {
        "Criterion #": "2",
        "Criterion": "Second",
        "Max Score": "7",
        "Satisfaction (%)": "100.0",
        "Score Awarded": "2.72",
        "Rationale": "B",}
    assert result[1] == expected_r2

    out = capsys.readouterr().out
    assert f"Wrote CSV report to {out_csv}" in out

def test_run_raises_on_length_mismatch(tmp_path, monkeypatch):
    #length mismatch
    tested = EvalReportGenerator
    rubric = [{"criterion": "X", "weight": 5}]
    scores = [
        {"satisfaction": 1, "score": 1, "rationale": "x"},
        {"satisfaction": 2, "score": 2, "rationale": "y"},
    ]
    rubric_path = _write_json(tmp_path, rubric, "r.json")
    scores_path = _write_json(tmp_path, scores, "s.json")
    out_csv     = tmp_path / "o.csv"

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--rubric", str(rubric_path),
        "--scores", str(scores_path),
        "--out",    str(out_csv),
    ])

    with pytest.raises(ValueError) as exc:
        tested.run()
    assert "Rubric and score arrays must have the same length." in str(exc.value)

def test_run_calls_load_json_exactly_twice(tmp_path, monkeypatch):
    tested = EvalReportGenerator
    calls = []
    def fake_load_json(cls, path):
        calls.append(path)
        # return single‐item lists so lengths match
        if "rub" in path.name:
            return [{"criterion": "C", "weight": 1}]
        return [{"satisfaction": 0, "score": 0, "rationale": ""}]

    monkeypatch.setattr(
        tested,
        "load_json",
        classmethod(fake_load_json),
    )

    rubric_path = _write_json(tmp_path, [{"criterion": "C", "weight": 1}], "rubric.json")
    scores_path = _write_json(tmp_path, [{"satisfaction": 0, "score": 0, "rationale": ""}], "scores.json")
    out_csv     = tmp_path / "out.csv"

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--rubric", str(rubric_path),
        "--scores", str(scores_path),
        "--out",    str(out_csv),
    ])

    EvalReportGenerator.run()
    expected = ["rubric.json", "scores.json"]
    result = [path.name for path in calls]
    assert result == expected
    assert len(calls) == 2
    assert calls == [rubric_path, scores_path]
