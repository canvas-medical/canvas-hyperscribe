import hashlib
import json
from unittest.mock import patch, call, MagicMock

import pytest

from evaluations.case_builders.note_grader import NoteGrader
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.graded_criterion import GradedCriterion
from evaluations.structures.records.experiment_result_score import ExperimentResultScore
from evaluations.structures.records.score import Score as ScoreRecord
from evaluations.structures.rubric_criterion import RubricCriterion
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockClass


@pytest.fixture
def tmp_files(tmp_path):
    rubric = [
        {"criterion": "Reward for A", "weight": 20},
        {"criterion": "Reward for B", "weight": 30},
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
    rubric_objs = RubricCriterion.load_from_json(rubric)
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

    _, _, _, rubric, note = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = RubricCriterion.load_from_json(rubric)
    tested = NoteGrader(vendor_key, rubric_objs, note)
    expected_schema = {"type": "array"}
    mock_schema_scores.side_effect = [expected_schema]

    result_system_lines, result_user_lines = tested.build_prompts()
    expected_system_prompt_md5 = "83ffb4b2602834cb84415885685311cc"
    expected_user_prompt_md5 = "26789d5126d246cb239032a16e9d0346"

    result_system_prompt_md5 = hashlib.md5("\n".join(result_system_lines).encode()).hexdigest()
    result_user_prompt_md5 = hashlib.md5("\n".join(result_user_lines).encode()).hexdigest()

    assert result_system_prompt_md5 == expected_system_prompt_md5
    assert result_user_prompt_md5 == expected_user_prompt_md5
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

    _, _, _, rubric, note = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    rubric_objs = RubricCriterion.load_from_json(rubric)
    tested = NoteGrader(vendor_key, rubric_objs, note)
    expected_schema = {"type": "array"}

    test_cases = [
        # success case
        {
            "generate_json_response": [
                GradedCriterion(id=0, rationale="good", satisfaction=80, score=0.0),
                GradedCriterion(id=1, rationale="bad", satisfaction=25, score=0.0),
            ],
            "expected": [
                GradedCriterion(id=0, rationale="good", satisfaction=80, score=16.0),
                GradedCriterion(id=1, rationale="bad", satisfaction=25, score=7.5),
            ],
        },
        # different scores case
        {
            "generate_json_response": [
                GradedCriterion(id=0, rationale="excellent", satisfaction=100, score=0.0),
                GradedCriterion(id=1, rationale="poor", satisfaction=0, score=0.0),
            ],
            "expected": [
                GradedCriterion(id=0, rationale="excellent", satisfaction=100, score=20.0),
                GradedCriterion(id=1, rationale="poor", satisfaction=0, score=0.0),
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
                system_prompt=["System Prompt"],
                user_prompt=["User Prompt"],
                schema=expected_schema,
                returned_class=GradedCriterion,
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
    expected_call = [
        call(
            system_prompt=["System Prompt"],
            user_prompt=["User Prompt"],
            schema=expected_schema,
            returned_class=GradedCriterion,
        )
    ]
    assert mock_generate_json.mock_calls == expected_call
    reset_mocks()


@patch("evaluations.case_builders.note_grader.HelperEvaluation")
@patch("evaluations.case_builders.note_grader.ExperimentResultScoreDatastore")
@patch("evaluations.case_builders.note_grader.RubricDatastore")
@patch("evaluations.case_builders.note_grader.GeneratedNoteDatastore")
@patch("evaluations.case_builders.note_grader.ScoreDatastore")
@patch.object(NoteGrader, "run")
def test_grade_and_save2database(
    mock_run,
    mock_score_datastore,
    mock_generated_note_datastore,
    mock_rubric_datastore,
    mock_experiment_result_datastore,
    mock_helper,
):
    tested = NoteGrader

    def reset_mocks():
        mock_run.reset_mock()
        mock_score_datastore.reset_mock()
        mock_generated_note_datastore.reset_mock()
        mock_rubric_datastore.reset_mock()
        mock_experiment_result_datastore.reset_mock()
        mock_helper.reset_mock()

    vendor_key = VendorKey(vendor="openai", api_key="test_key")
    # Mock data
    rubric_data = [{"criterion": "Test criterion", "weight": 10}]
    note_data = {"some": "note"}
    grading_result = [GradedCriterion(id=0, rationale="good work", satisfaction=85, score=8.5)]

    tests = [
        (0, False, []),
        (
            37,
            True,
            [
                call("thePostgresCredentials"),
                call().insert(
                    ExperimentResultScore(
                        experiment_result_id=37,
                        score_id=781,
                        scoring_result=[GradedCriterion(id=0, rationale="good work", satisfaction=85, score=8.5)],
                        id=0,
                    )
                ),
            ],
        ),
    ]
    for experiment_result_id, exp_experiment, exp_calls in tests:
        expected = MockClass(id=781)
        mock_rubric_datastore.return_value.get_rubric.side_effect = [rubric_data]
        mock_generated_note_datastore.return_value.get_note_json.side_effect = [note_data]
        mock_run.side_effect = [grading_result]
        mock_helper.settings.side_effect = [MockClass(llm_text=vendor_key)]
        mock_helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
        mock_score_datastore.return_value.insert.side_effect = [expected]

        # Call the method
        result = tested.grade_and_save2database(123, 456, experiment_result_id)
        assert result == expected

        # verify mock calls + score_datastore.insert + attributes.
        calls = [call()]
        assert mock_run.mock_calls == calls
        calls = [
            call("thePostgresCredentials"),
            call().insert(
                ScoreRecord(
                    rubric_id=123,
                    generated_note_id=456,
                    scoring_result=[GradedCriterion(id=0, rationale="good work", satisfaction=85, score=8.5)],
                    overall_score=8.5,
                    comments="",
                    text_llm_vendor="openai",
                    text_llm_name="o3",
                    temperature=1.0,
                    experiment=exp_experiment,
                    id=0,
                )
            ),
        ]
        assert mock_score_datastore.mock_calls == calls
        calls = [
            call("thePostgresCredentials"),
            call().get_note_json(456),
        ]
        assert mock_generated_note_datastore.mock_calls == calls
        calls = [
            call("thePostgresCredentials"),
            call().get_rubric(123),
        ]
        assert mock_rubric_datastore.mock_calls == calls
        assert mock_experiment_result_datastore.mock_calls == exp_calls
        calls = [
            call.postgres_credentials(),
            call.settings(),
        ]
        assert mock_helper.mock_calls == calls
        reset_mocks()


@patch.object(HelperEvaluation, "settings")
@patch.object(NoteGrader, "load_json")
@patch.object(NoteGrader, "run")
def test_grade_and_save2file(mock_run, mock_load_json, mock_settings, tmp_path, capsys):
    tested = NoteGrader
    vendor_key = VendorKey(vendor="openai", api_key="test_key")

    def reset_mocks():
        mock_run.reset_mock()
        mock_load_json.reset_mock()
        mock_settings.reset_mock()

    # Create test files
    rubric_path = tmp_path / "rubric.json"
    note_path = tmp_path / "note.json"
    output_path = tmp_path / "output.json"

    # Mock data
    rubric_data = [{"criterion": "Test criterion", "weight": 10}]
    note_data = {"some": "note"}
    grading_result = [GradedCriterion(id=0, rationale="good work", satisfaction=85, score=8.5)]

    mock_load_json.side_effect = [rubric_data, note_data]
    mock_run.side_effect = [grading_result]
    mock_settings.side_effect = [MagicMock(llm_text=vendor_key)]

    tested.grade_and_save2file(rubric_path, note_path, output_path)

    # Verify mock calls in reset_mocks order
    assert mock_run.mock_calls == [call()]
    assert mock_load_json.mock_calls == [call(rubric_path), call(note_path)]
    assert mock_settings.mock_calls == [call()]

    # Verify output file was written
    assert output_path.exists()
    result = json.loads(output_path.read_text())
    # Compare with expected grading result structure
    expected = [{"id": 0, "rationale": "good work", "satisfaction": 85, "score": 8.5}]
    assert result == expected

    # Verify print output
    output = capsys.readouterr().out.strip()
    assert f"Saved grading result in {output_path}" == output

    reset_mocks()


@patch("evaluations.case_builders.note_grader.argparse.ArgumentParser")
def test_main(mock_parser_class, tmp_path, capsys):
    tested = NoteGrader
    mock_parser = MagicMock()

    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    mock_parser_class.side_effect = [mock_parser]

    test_cases = [
        # File mode
        {
            "args": MockClass(
                rubric=tmp_path / "rubric.json",
                note=tmp_path / "note.json",
                output=tmp_path / "out.json",
                rubric_id=None,
                generated_note_id=None,
                experiment_result_id=None,
            ),
            "expected_method": "grade_and_save2file",
        },
        # Database mode
        {
            "args": MockClass(
                rubric=None,
                note=None,
                output=None,
                rubric_id=123,
                generated_note_id=456,
                experiment_result_id=789,
            ),
            "expected_method": "grade_and_save2database",
        },
    ]

    for test_case in test_cases:
        mock_parser.parse_args.side_effect = [test_case["args"]]

        if test_case["expected_method"] == "grade_and_save2file":
            with patch.object(tested, "grade_and_save2file") as mock_method:
                tested.main()
                assert mock_method.mock_calls == [
                    call(
                        tmp_path / "rubric.json",
                        tmp_path / "note.json",
                        tmp_path / "out.json",
                    )
                ]
        else:
            mock_score_record = MagicMock()
            mock_score_record.id = 789
            with patch.object(tested, "grade_and_save2database") as mock_method:
                mock_method.side_effect = [mock_score_record]
                tested.main()
                assert mock_method.mock_calls == [call(123, 456, 789)]
                output = capsys.readouterr().out
                assert f"Saved grading result to database with score ID: {mock_score_record.id}" in output

        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    # Test parameter validation cases
    validation_test_cases = [
        # Missing parameters
        {
            "args": MockClass(rubric=None, note=None, output=None, rubric_id=None, generated_note_id=None),
            "expected_error": "Must provide either (--rubric, --note, --output) or (--rubric_id, --generated_note_id)",
        },
        # Conflicting parameters
        {
            "args": MockClass(
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
