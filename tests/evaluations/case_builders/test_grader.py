import json
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from evaluations.case_builders.note_grader import NoteGrader
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.structures.rubric_criterion import RubricCriterion

@pytest.fixture
def tmp_files(tmp_path):
    rubric = [
        {"criterion": "Reward for A",  "weight": 20, "sense": "positive"},
        {"criterion": "Penalize for B","weight": 30, "sense": "negative"},
    ]
    note = {"some": "note"}

    rubric_path = tmp_path / "rubric.json"
    note_path   = tmp_path / "note.json"
    output_path = tmp_path / "out.json"
    rubric_path.write_text(json.dumps(rubric))
    note_path.write_text(json.dumps(note))
    return rubric_path, note_path, output_path, rubric, note

@patch("evaluations.case_builders.grader.generate_json")
def test_run_happy_path(mock_generate_json, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    expected = [
        {"rationale": "good", "satisfaction": 80.0,  "score": 16.0},
        {"rationale": "bad",  "satisfaction": 25.0, "score": -22.5},
    ]
    mock_generate_json.return_value = [
        {"rationale": "good", "satisfaction": 80},
        {"rationale": "bad",  "satisfaction": 25},
    ]

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    NoteGrader(vendor_key=vendor_key, rubric=rubric_objs,
        note=note, output_path=output_path).run()

    result = json.loads(output_path.read_text())
    assert result == expected

    # Ensure generate_json was called once with correct kwargs
    mock_generate_json.assert_called_once()
    _, kwargs = mock_generate_json.call_args
    assert kwargs["vendor_key"] is vendor_key
    assert kwargs["retries"] == 3

    schema = kwargs["schema"]
    assert schema["minItems"] == len(rubric)
    assert schema["maxItems"] == len(rubric)

@patch("evaluations.case_builders.grader.generate_json", side_effect=SystemExit(1))
def test_run_raises_on_generate_failure(mock_generate_json, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**rubric[0])]
    tested = NoteGrader(
        vendor_key=vendor_key,
        rubric=rubric_objs,
        note={},
        output_path=output_path
    )

    with pytest.raises(SystemExit) as exc_info:
        tested.run()

    assert exc_info.value.code == 1
    mock_generate_json.assert_called_once()

def test_main_parses_args_and_invokes_run(monkeypatch, tmp_path):
    tested = NoteGrader.main

    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey(vendor="test", api_key="MY_API_KEY")
    monkeypatch.setattr(
        "evaluations.case_builders.grader.Settings.from_dictionary",
        classmethod(lambda cls, env: dummy_settings)
    )

    rubric_data = [{"criterion": "X", "weight": 1, "sense": "positive"}]
    note_data = {"foo": "bar"}

    rubric_file = tmp_path / "rubric.json"
    note_file = tmp_path / "note.json"
    out_file = tmp_path / "out.json"
    rubric_file.write_text(json.dumps(rubric_data))
    note_file.write_text(json.dumps(note_data))

    run_calls = {}

    def fake_run(self):
        run_calls["self"] = self
        run_calls["called"] = True

    monkeypatch.setattr(NoteGrader, "run", fake_run)

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--rubric", str(rubric_file),
        "--note",   str(note_file),
        "--output", str(out_file),
    ])

    tested()

    #testing calls
    assert run_calls.get("called") is True
    assert isinstance(run_calls["self"], NoteGrader)
    assert run_calls["self"].vendor_key.api_key == "MY_API_KEY"