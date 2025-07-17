import json
import sys
from pathlib import Path
from argparse import Namespace
import pytest
from unittest.mock import patch, MagicMock, call

from evaluations.case_builders.note_grader import NoteGrader, HelperEvaluation
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

@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json")
def test_run__success(mock_generate_json, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    expected = [
        {"rationale": "good", "satisfaction": 80.0,  "score": 16.0},
        {"rationale": "bad",  "satisfaction": 25.0, "score": -22.5},
    ]
    mock_generate_json.side_effect = [[
        {"id": 0, "rationale": "good", "satisfaction": 80},
        {"id": 1, "rationale": "bad",  "satisfaction": 25},
    ]]

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    grader = NoteGrader(vendor_key=vendor_key, rubric=rubric_objs,
        note=note, output_path=output_path)

    system_prompt, user_prompt = grader.build_prompts()
    schema = grader.schema_scores()
    grader.run()

    result = json.loads(output_path.read_text())
    expected = [
        {"rationale": "good", "satisfaction": 80, "score": 16.0},
        {"rationale": "bad",  "satisfaction": 25, "score": -22.5},
    ]
    assert result == expected

    # ensure generate_json got exactly the call we expected
    expected_call = call(
        vendor_key=vendor_key,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=schema)
    assert mock_generate_json.mock_calls == [expected_call]

@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json", side_effect=SystemExit(1))
def test_run__raises_on_generate_failure(mock_generate_json, tmp_files):
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

def test_main(tmp_path):
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey(vendor="test", api_key="MY_API_KEY")

    rubric_data = [{"criterion": "X", "weight": 1, "sense": "positive"}]
    note_data   = {"foo": "bar"}
    rubric_file = tmp_path / "rubric.json"
    note_file   = tmp_path / "note.json"
    out_file    = tmp_path / "out.json"
    rubric_file.write_text(json.dumps(rubric_data))
    note_file.write_text(json.dumps(note_data))

    fake_args = Namespace(
        rubric=rubric_file,
        note=note_file,
        output=out_file)

    run_calls = {}
    def fake_run(self):
        run_calls["inst"] = self
        run_calls["called"] = True

    with patch.object(HelperEvaluation, "settings", classmethod(lambda cls: dummy_settings)), \
         patch("evaluations.case_builders.note_grader.argparse.ArgumentParser.parse_args", return_value=fake_args), \
         patch.object(NoteGrader, "run", fake_run):
         NoteGrader.main()

    assert run_calls.get("called") is True
    inst = run_calls["inst"]
    assert isinstance(inst, NoteGrader)
    assert inst.vendor_key.api_key == "MY_API_KEY"

    # confirm it read & wrapped the rubric correctly
    assert inst.rubric == [RubricCriterion(**rubric_data[0])]
    assert inst.note == note_data
    assert inst.output_path == out_file