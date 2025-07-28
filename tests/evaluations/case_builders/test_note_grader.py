import json, pytest, hashlib
from argparse import Namespace
from unittest.mock import patch, MagicMock, call

from evaluations.case_builders.note_grader import NoteGrader, HelperEvaluation
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.structures.rubric_criterion import RubricCriterion


@pytest.fixture
def tmp_files(tmp_path):
    rubric = [
        {"criterion": "Reward for A", "weight": 20, "sense": "positive"},
        {"criterion": "Penalize for B", "weight": 30, "sense": "negative"},
    ]
    note = {"some": "note"}

    rubric_path = tmp_path / "rubric.json"
    note_path = tmp_path / "note.json"
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
    tested = NoteGrader(vendor_key=VendorKey("openai", "KEY"), rubric=rubric, note=note)

    result = tested.schema_scores()
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 2,
        "maxItems": 2,
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "index to match criteria"},
                "rationale": {"type": "string", "description": "reasoning for satisfaction score"},
                "satisfaction": {"type": "integer", "description": "note grade", "minimum": 0, "maximum": 100},
            },
            "required": ["id", "rationale", "satisfaction"],
            "additionalProperties": False,
        },
    }

    assert result == expected


@patch.object(NoteGrader, "schema_scores")
def test_build_prompts(mock_schema_scores, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    tested = NoteGrader(vendor_key, rubric_objs, note)
    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = lambda: expected_schema

    result_system_lines, result_user_lines = tested.build_prompts()
    expected_system_md5 = "83ffb4b2602834cb84415885685311cc"
    expected_user_md5 = "a5094e3da8bdeea48d768b26024ef00a"

    result_system_md5 = hashlib.md5("\n".join(result_system_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(result_user_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
    assert mock_schema_scores.mock_calls == [call()]


@patch.object(NoteGrader, "build_prompts", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(NoteGrader, "schema_scores")
@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json")
def test_run__success(mock_generate_json, mock_schema_scores, mock_build_prompts, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    expected = [
        {"id": 0, "rationale": "good", "satisfaction": 80.0, "score": 16.0},
        {"id": 1, "rationale": "bad", "satisfaction": 25.0, "score": -22.5},
    ]
    mock_generate_json.side_effect = [
        [
            {"id": 0, "rationale": "good", "satisfaction": 80},
            {"id": 1, "rationale": "bad", "satisfaction": 25},
        ]
    ]

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = lambda: expected_schema
    grader = NoteGrader(vendor_key, rubric_objs, note)
    result = grader.run()
    assert result == expected

    assert mock_schema_scores.mock_calls == [call()]
    assert mock_build_prompts.mock_calls == [call()]

    # ensure generate_json got exactly the call we expected
    assert mock_generate_json.call_count == 1
    expected_call = [
        call(
            vendor_key=vendor_key,
            system_prompt=["System Prompt"],
            user_prompt=["User Prompt"],
            schema=expected_schema,
        )
    ]
    assert mock_generate_json.mock_calls == expected_call


@patch.object(NoteGrader, "build_prompts", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(NoteGrader, "schema_scores")
@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json", side_effect=SystemExit(1))
def test_run__raises_on_generate_failure(mock_generate_json, mock_schema_scores, mock_build_prompts, tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**rubric[0])]
    tested = NoteGrader(vendor_key=vendor_key, rubric=rubric_objs, note={})

    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = lambda: expected_schema

    with pytest.raises(SystemExit) as exc_info:
        tested.run()

    assert mock_schema_scores.mock_calls == [call()]
    assert mock_build_prompts.mock_calls == [call()]
    assert exc_info.value.code == 1
    assert mock_generate_json.call_count == 1
    expected_call = call(
        vendor_key=vendor_key,
        system_prompt=["System Prompt"],
        user_prompt=["User Prompt"],
        schema=expected_schema,
    )
    assert mock_generate_json.mock_calls == [expected_call]


def test_main(tmp_path):
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey(vendor="test", api_key="MY_API_KEY")

    rubric_data = [{"criterion": "X", "weight": 1, "sense": "positive"}]
    note_data = {"foo": "bar"}
    rubric_file = tmp_path / "rubric.json"
    note_file = tmp_path / "note.json"
    out_file = tmp_path / "out.json"
    rubric_file.write_text(json.dumps(rubric_data))
    note_file.write_text(json.dumps(note_data))

    fake_args = Namespace(rubric=rubric_file, note=note_file, output=out_file)

    run_calls = {}
    fake_result = [{"id": 0, "rationale": "test", "satisfaction": 85, "score": 0.85}]

    def fake_run(self):
        run_calls["instance"] = self
        run_calls["called"] = True
        return fake_result

    with (
        patch.object(HelperEvaluation, "settings", classmethod(lambda cls: dummy_settings)),
        patch("evaluations.case_builders.note_grader.argparse.ArgumentParser.parse_args", return_value=fake_args),
        patch.object(NoteGrader, "run", fake_run),
    ):
        NoteGrader.main()

    assert run_calls.get("called") is True
    instance = run_calls["instance"]
    # instance check for each component
    assert isinstance(instance, NoteGrader)
    assert instance.vendor_key.api_key == "MY_API_KEY"
    assert instance.rubric == [RubricCriterion(**rubric_data[0])]
    assert instance.note == note_data

    # Check that the output file was written with the result from run()
    result_written = json.loads(out_file.read_text())
    assert result_written == fake_result


@patch("evaluations.case_builders.note_grader.HelperEvaluation.postgres_credentials")
@patch("evaluations.case_builders.note_grader.HelperEvaluation.settings")
@patch("evaluations.case_builders.note_grader.RubricDatastore")
@patch("evaluations.case_builders.note_grader.GeneratedNoteDatastore")
@patch("evaluations.case_builders.note_grader.ScoreDatastore")
@patch.object(NoteGrader, "run")
def test_grade_and_save(
    mock_run,
    mock_score_ds_class,
    mock_generated_note_ds_class,
    mock_rubric_ds_class,
    mock_settings,
    mock_postgres_credentials,
):
    # Mock credentials
    mock_credentials = MagicMock()
    mock_postgres_credentials.return_value = mock_credentials

    # Mock settings
    mock_vendor_key = VendorKey(vendor="openai", api_key="test_key")
    mock_settings.return_value.llm_text = mock_vendor_key

    # Mock datastores
    mock_rubric_ds = MagicMock()
    mock_generated_note_ds = MagicMock()
    mock_score_ds = MagicMock()
    mock_rubric_ds_class.return_value = mock_rubric_ds
    mock_generated_note_ds_class.return_value = mock_generated_note_ds
    mock_score_ds_class.return_value = mock_score_ds

    # Mock data
    rubric_data = [{"criterion": "Test criterion", "weight": 10, "sense": "positive"}]
    note_data = {"some": "note"}
    grading_result = [{"id": 0, "rationale": "good work", "satisfaction": 85, "score": 8.5}]

    mock_rubric_ds.get_rubric.return_value = rubric_data
    mock_generated_note_ds.get_note_json.return_value = note_data
    mock_run.return_value = grading_result

    # Mock score record
    expected_score_record = MagicMock()
    expected_score_record.id = 789
    mock_score_ds.insert.return_value = expected_score_record

    # Call the method
    result = NoteGrader.grade_and_save(123, 456)

    # Assertions
    assert result == expected_score_record

    # Verify datastore instantiation calls
    mock_rubric_ds_class.assert_called_once_with(mock_credentials)
    mock_generated_note_ds_class.assert_called_once_with(mock_credentials)
    mock_score_ds_class.assert_called_once_with(mock_credentials)

    # Verify datastore method calls
    mock_rubric_ds.get_rubric.assert_called_once_with(123)
    mock_generated_note_ds.get_note_json.assert_called_once_with(456)
    mock_run.assert_called_once()

    # Verify score record creation and insertion
    assert mock_score_ds.insert.call_count == 1
    score_record_arg = mock_score_ds.insert.call_args[0][0]
    assert score_record_arg.rubric_id == 123
    assert score_record_arg.generated_note_id == 456
    assert score_record_arg.overall_score == 8.5
    assert score_record_arg.text_llm_vendor == "openai"
    assert score_record_arg.scoring_result == grading_result
