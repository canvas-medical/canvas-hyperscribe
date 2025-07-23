import json, pytest, hashlib
from argparse import Namespace
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

def test_load_json(tmp_path):
    expected = {"hello": "world"}
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(expected))

    result = NoteGrader.load_json(path)
    assert result == expected

def test_schema_scores(tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files
    tested = NoteGrader(vendor_key=VendorKey("openai", "KEY"), rubric=rubric, note=note,
        output_path=None)

    result = tested.schema_scores()
    expected = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer",
                           "description": "index to match criteria"},
                    "rationale": {"type": "string",
                                  "description": "reasoning for satisfaction score"},
                    "satisfaction":{"type": "integer", 
                                    "description": "note grade",
                                    "minimum": 0, 
                                    "maximum": 100}
                },
                "required": ["id", "rationale", "satisfaction"],
                "additionalProperties": False
            }
        }

    assert result == expected

@patch.object(NoteGrader, "schema_scores")
def test_build_prompts(mock_schema_scores, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    tested = NoteGrader(vendor_key, rubric_objs, note, output_path)
    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = lambda: expected_schema


    result_system_lines, result_user_lines = tested.build_prompts()
    expected_system_md5 = "83ffb4b2602834cb84415885685311cc"
    expected_user_md5 = "a5094e3da8bdeea48d768b26024ef00a"

    result_system_md5 = hashlib.md5("\n".join(result_system_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(result_user_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5


@patch.object(NoteGrader, "build_prompts", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(NoteGrader, "schema_scores")
@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json")
def test_run__success(mock_generate_json, mock_schema_scores, mock_build_prompts, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    expected = [
        {"id": 0, "rationale": "good", "satisfaction": 80.0,  "score": 16.0},
        {"id": 1, "rationale": "bad",  "satisfaction": 25.0, "score": -22.5},
    ]
    mock_generate_json.side_effect = [[
        {"id": 0, "rationale": "good", "satisfaction": 80},
        {"id": 1, "rationale": "bad",  "satisfaction": 25},
    ]]

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = lambda: expected_schema
    grader = NoteGrader(vendor_key, rubric_objs, note, output_path)
    grader.run()

    result = json.loads(output_path.read_text())
    assert result == expected

    # ensure generate_json got exactly the call we expected
    assert mock_generate_json.call_count == 1
    expected_call = call(
        vendor_key=vendor_key,
        system_prompt=["System Prompt"],
        user_prompt=["User Prompt"],
        schema=expected_schema)
    assert mock_generate_json.mock_calls == [expected_call]


@patch.object(NoteGrader, "build_prompts", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(NoteGrader, "schema_scores")
@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json", side_effect=SystemExit(1))
def test_run__raises_on_generate_failure(mock_generate_json, mock_schema_scores, mock_build_prompts, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**rubric[0])]
    tested = NoteGrader(
        vendor_key=vendor_key,
        rubric=rubric_objs,
        note={},
        output_path=output_path
    )

    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = lambda: expected_schema

    with pytest.raises(SystemExit) as exc_info:
        tested.run()

    assert exc_info.value.code == 1
    assert mock_generate_json.call_count == 1
    expected_call = call(
        vendor_key=vendor_key,
        system_prompt=["System Prompt"],
        user_prompt=["User Prompt"],
        schema=expected_schema
    )
    assert mock_generate_json.mock_calls == [expected_call]

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
        run_calls["instance"] = self
        run_calls["called"] = True

    with patch.object(HelperEvaluation, "settings", classmethod(lambda cls: dummy_settings)), \
         patch("evaluations.case_builders.note_grader.argparse.ArgumentParser.parse_args", return_value=fake_args), \
         patch.object(NoteGrader, "run", fake_run):
         NoteGrader.main()

    assert run_calls.get("called") is True
    instance = run_calls["instance"]
     #instance check for each component
    assert isinstance(instance, NoteGrader)
    assert instance.vendor_key.api_key == "MY_API_KEY"
    assert instance.rubric == [RubricCriterion(**rubric_data[0])]
    assert instance.note == note_data
    assert instance.output_path == out_file