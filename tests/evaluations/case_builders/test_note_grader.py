import hashlib
import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

import pytest

from evaluations.case_builders.note_grader import NoteGrader
from evaluations.structures.rubric_criterion import RubricCriterion
from hyperscribe.structures.vendor_key import VendorKey


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
    tested = NoteGrader

    test_cases = [{"hello": "world"}, [{"item": "value"}], {"complex": {"nested": ["data"]}}]

    for expected in test_cases:
        path = tmp_path / f"sample_{hash(str(expected))}.json"
        path.write_text(json.dumps(expected))

        result = tested.load_json(path)
        assert result == expected


def test_schema_scores(tmp_files):
    rubric_path, note_path, output_path, rubric, note = tmp_files
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    tested = NoteGrader(vendor_key=VendorKey("openai", "KEY"), rubric=rubric_objs, note=note)

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
    def reset_mocks():
        mock_schema_scores.reset_mock()

    rubric_path, note_path, output_path, rubric, note = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    tested = NoteGrader(vendor_key, rubric_objs, note)
    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = [expected_schema]

    result_system_lines, result_user_lines = tested.build_prompts()
    expected_system_md5 = "83ffb4b2602834cb84415885685311cc"
    expected_user_md5 = "a5094e3da8bdeea48d768b26024ef00a"

    result_system_md5 = hashlib.md5("\n".join(result_system_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(result_user_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
    assert mock_schema_scores.mock_calls == [call()]
    reset_mocks()


@patch.object(NoteGrader, "build_prompts")
@patch.object(NoteGrader, "schema_scores")
@patch("evaluations.case_builders.note_grader.HelperSyntheticJson.generate_json")
def test_run(mock_generate_json, mock_schema_scores, mock_build_prompts, tmp_files):
    def reset_mocks():
        mock_generate_json.reset_mock()
        mock_schema_scores.reset_mock()
        mock_build_prompts.reset_mock()

    rubric_path, note_path, output_path, rubric, note = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = [RubricCriterion(**item) for item in rubric]
    tested = NoteGrader(vendor_key, rubric_objs, note)
    expected_schema = {"type": "array"}

    test_cases = [
        # success case
        {
            "generate_json_response": [
                {"id": 0, "rationale": "good", "satisfaction": 80},
                {"id": 1, "rationale": "bad", "satisfaction": 25},
            ],
            "expected": [
                {"id": 0, "rationale": "good", "satisfaction": 80, "score": 16.0},
                {"id": 1, "rationale": "bad", "satisfaction": 25, "score": -22.5},
            ],
        },
        # different scores case
        {
            "generate_json_response": [
                {"id": 0, "rationale": "excellent", "satisfaction": 100},
                {"id": 1, "rationale": "poor", "satisfaction": 0},
            ],
            "expected": [
                {"id": 0, "rationale": "excellent", "satisfaction": 100, "score": 20.0},
                {"id": 1, "rationale": "poor", "satisfaction": 0, "score": -30.0},
            ],
        },
    ]

    for test_case in test_cases:
        mock_build_prompts.side_effect = [(["System Prompt"], ["User Prompt"])]
        mock_schema_scores.side_effect = [expected_schema]
        mock_generate_json.side_effect = [test_case["generate_json_response"]]

        result = tested.run()
        expected = test_case["expected"]
        assert result == expected

        calls = [call()]
        assert mock_schema_scores.mock_calls == calls
        assert mock_build_prompts.mock_calls == calls

        expected_call = [
            call(
                vendor_key=vendor_key,
                system_prompt=["System Prompt"],
                user_prompt=["User Prompt"],
                schema=expected_schema,
            )
        ]
        assert mock_generate_json.mock_calls == expected_call
        reset_mocks()

    # test exception case
    mock_build_prompts.side_effect = [(["System Prompt"], ["User Prompt"])]
    mock_schema_scores.side_effect = [expected_schema]
    mock_generate_json.side_effect = [SystemExit(1)]

    with pytest.raises(SystemExit) as exc_info:
        tested.run()

    assert exc_info.value.code == 1
    assert mock_schema_scores.mock_calls == [call()]
    assert mock_build_prompts.mock_calls == [call()]
    assert mock_generate_json.call_count == 1
    reset_mocks()


@patch("evaluations.case_builders.note_grader.HelperEvaluation.postgres_credentials")
@patch("evaluations.case_builders.note_grader.HelperEvaluation.settings")
@patch("evaluations.case_builders.note_grader.RubricDatastore")
@patch("evaluations.case_builders.note_grader.GeneratedNoteDatastore")
@patch("evaluations.case_builders.note_grader.ScoreDatastore")
@patch.object(NoteGrader, "run")
def test_grade_and_save2database(
    mock_run,
    mock_score_ds_class,
    mock_generated_note_ds_class,
    mock_rubric_ds_class,
    mock_settings,
    mock_postgres_credentials,
):
    def reset_mocks():
        mock_run.reset_mock()
        mock_score_ds_class.reset_mock()
        mock_generated_note_ds_class.reset_mock()
        mock_rubric_ds_class.reset_mock()
        mock_settings.reset_mock()
        mock_postgres_credentials.reset_mock()
        mock_credentials.reset_mock()
        mock_rubric_ds.reset_mock()
        mock_generated_note_ds.reset_mock()
        mock_score_ds.reset_mock()
        mock_score_record.reset_mock()

    tested = NoteGrader

    # Mock credentials
    mock_credentials = MagicMock()
    mock_postgres_credentials.side_effect = [mock_credentials]

    # Mock settings
    mock_vendor_key = VendorKey(vendor="openai", api_key="test_key")
    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]

    # Mock datastores
    mock_rubric_ds = MagicMock()
    mock_generated_note_ds = MagicMock()
    mock_score_ds = MagicMock()
    mock_rubric_ds_class.side_effect = [mock_rubric_ds]
    mock_generated_note_ds_class.side_effect = [mock_generated_note_ds]
    mock_score_ds_class.side_effect = [mock_score_ds]

    # Mock data
    rubric_data = [{"criterion": "Test criterion", "weight": 10, "sense": "positive"}]
    note_data = {"some": "note"}
    grading_result = [{"id": 0, "rationale": "good work", "satisfaction": 85, "score": 8.5}]

    mock_rubric_ds.get_rubric.side_effect = [rubric_data]
    mock_generated_note_ds.get_note_json.side_effect = [note_data]
    mock_run.side_effect = [grading_result]

    # Mock score record
    mock_score_record = MagicMock()
    mock_score_record.id = 789
    mock_score_ds.insert.side_effect = [mock_score_record]

    # Call the method
    result = tested.grade_and_save2database(123, 456)
    expected = mock_score_record

    # Assertions
    assert result == expected

    # Verify calls
    assert mock_postgres_credentials.mock_calls == [call()]
    assert mock_settings.mock_calls == [call()]
    assert mock_rubric_ds_class.mock_calls == [call(mock_credentials)]
    assert mock_generated_note_ds_class.mock_calls == [call(mock_credentials)]
    assert mock_score_ds_class.mock_calls == [call(mock_credentials)]
    assert mock_rubric_ds.get_rubric.mock_calls == [call(123)]
    assert mock_generated_note_ds.get_note_json.mock_calls == [call(456)]
    assert mock_run.mock_calls == [call()]

    # Verify score record creation and insertion
    assert mock_score_ds.insert.call_count == 1
    score_record_arg = mock_score_ds.insert.call_args[0][0]
    assert score_record_arg.rubric_id == 123
    assert score_record_arg.generated_note_id == 456
    assert score_record_arg.overall_score == 8.5
    assert score_record_arg.text_llm_vendor == "openai"
    assert score_record_arg.scoring_result == grading_result

    reset_mocks()


@patch("evaluations.case_builders.note_grader.HelperEvaluation.settings")
@patch.object(NoteGrader, "load_json")
@patch.object(NoteGrader, "run")
def test_grade_and_save2file(mock_run, mock_load_json, mock_settings, tmp_path, capsys):
    def reset_mocks():
        mock_run.reset_mock()
        mock_load_json.reset_mock()
        mock_settings.reset_mock()
        mock_settings_instance.reset_mock()

    tested = NoteGrader

    # Mock settings
    mock_vendor_key = VendorKey(vendor="openai", api_key="test_key")
    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]

    # Create test files
    rubric_path = tmp_path / "rubric.json"
    note_path = tmp_path / "note.json"
    output_path = tmp_path / "output.json"

    # Mock data
    rubric_data = [{"criterion": "Test criterion", "weight": 10, "sense": "positive"}]
    note_data = {"some": "note"}
    grading_result = [{"id": 0, "rationale": "good work", "satisfaction": 85, "score": 8.5}]

    mock_load_json.side_effect = [rubric_data, note_data]
    mock_run.side_effect = [grading_result]

    # Call the method
    tested.grade_and_save2file(rubric_path, note_path, output_path)

    # Verify calls
    assert mock_settings.mock_calls == [call()]
    assert mock_load_json.mock_calls == [call(rubric_path), call(note_path)]
    assert mock_run.mock_calls == [call()]

    # Verify output file was written
    assert output_path.exists()
    result = json.loads(output_path.read_text())
    expected = grading_result
    assert result == expected

    # Verify print output
    output = capsys.readouterr().out
    assert f"Saved grading result in {output_path}" == output

    reset_mocks()


@patch("evaluations.case_builders.note_grader.argparse.ArgumentParser")
def test_main(mock_parser_class, tmp_path, capsys):
    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    tested = NoteGrader
    mock_parser = MagicMock()
    mock_parser_class.side_effect = [mock_parser]

    test_cases = [
        # File mode
        {
            "args": Namespace(
                rubric=tmp_path / "rubric.json",
                note=tmp_path / "note.json",
                output=tmp_path / "out.json",
                rubric_id=None,
                generated_note_id=None,
            ),
            "expected_method": "grade_and_save2file",
        },
        # Database mode
        {
            "args": Namespace(rubric=None, note=None, output=None, rubric_id=123, generated_note_id=456),
            "expected_method": "grade_and_save2database",
        },
    ]

    for test_case in test_cases:
        mock_parser.parse_args.side_effect = [test_case["args"]]

        if test_case["expected_method"] == "grade_and_save2file":
            with patch.object(tested, "grade_and_save2file") as mock_method:
                tested.main()
                assert mock_method.mock_calls == [
                    call(test_case["args"].rubric, test_case["args"].note, test_case["args"].output)
                ]
        else:
            mock_score_record = MagicMock()
            mock_score_record.id = 789
            with patch.object(tested, "grade_and_save2database") as mock_method:
                mock_method.side_effect = [mock_score_record]
                tested.main()
                assert mock_method.mock_calls == [
                    call(test_case["args"].rubric_id, test_case["args"].generated_note_id)
                ]
                output = capsys.readouterr().out
                assert f"Saved grading result to database with score ID: {mock_score_record.id}" in output

        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    # Test parameter validation cases
    validation_test_cases = [
        # Missing parameters
        {
            "args": Namespace(rubric=None, note=None, output=None, rubric_id=None, generated_note_id=None),
            "expected_error": "Must provide either (--rubric, --note, --output) or (--rubric_id, --generated_note_id)",
        },
        # Conflicting parameters
        {
            "args": Namespace(
                rubric=tmp_path / "rubric.json",
                note=tmp_path / "note.json",
                output=tmp_path / "out.json",
                rubric_id=123,
                generated_note_id=456,
            ),
            "expected_error": "Cannot provide both file-based and database-based parameters",
        },
    ]

    for test_case in validation_test_cases:
        mock_parser.parse_args.side_effect = [test_case["args"]]
        mock_parser.error.side_effect = [SystemExit(2)]

        with pytest.raises(SystemExit):
            tested.main()

        assert mock_parser.error.mock_calls == [call(test_case["expected_error"])]
        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    reset_mocks()
