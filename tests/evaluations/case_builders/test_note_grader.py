import hashlib
import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

import pytest

from evaluations.case_builders.note_grader import NoteGrader
from evaluations.structures.graded_criterion import GradedCriterion
from evaluations.structures.records.experiment_result_score import ExperimentResultScore
from evaluations.structures.records.score import Score as ScoreRecord
from evaluations.structures.rubric_criterion import RubricCriterion
from hyperscribe.llms.llm_base import LlmBase
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
    tested = NoteGrader(rubric=rubric_objs, note=note)
    schema = tested.schema_scores()

    schema_hash = hashlib.md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "8b1858ddd1d12f945ac7c0db078d1245"
    assert schema_hash == expected_hash

    tests = [
        # Valid case with all required fields
        (
            [
                {"id": 0, "rationale": "Good work on A", "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement on B", "satisfaction": 60},
            ],
            "",
        ),
        # Empty array violation
        ([], "[] is too short"),
        # Too few items
        (
            [{"id": 0, "rationale": "Good work", "satisfaction": 85}],
            "[{'id': 0, 'rationale': 'Good work', 'satisfaction': 85}] is too short",
        ),
        # Too many items
        (
            [
                {"id": 0, "rationale": "Good work on A", "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement on B", "satisfaction": 60},
                {"id": 2, "rationale": "Extra item", "satisfaction": 70},
            ],
            "[{'id': 0, 'rationale': 'Good work on A', 'satisfaction': 85}, "
            "{'id': 1, 'rationale': 'Needs improvement on B', 'satisfaction': 60}, "
            "{'id': 2, 'rationale': 'Extra item', 'satisfaction': 70}] is too long",
        ),
        # Additional properties violation
        (
            [
                {"id": 0, "rationale": "Good work", "satisfaction": 85, "extra": "field"},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        # Missing required field: id
        (
            [
                {"rationale": "Good work", "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "'id' is a required property, in path [0]",
        ),
        # Missing required field: rationale
        (
            [
                {"id": 0, "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "'rationale' is a required property, in path [0]",
        ),
        # Missing required field: satisfaction
        (
            [
                {"id": 0, "rationale": "Good work"},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "'satisfaction' is a required property, in path [0]",
        ),
        # Type violation: id not integer
        (
            [
                {"id": "0", "rationale": "Good work", "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "'0' is not of type 'integer', in path [0, 'id']",
        ),
        # Type violation: rationale not string
        (
            [
                {"id": 0, "rationale": 123, "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "123 is not of type 'string', in path [0, 'rationale']",
        ),
        # Type violation: satisfaction not integer
        (
            [
                {"id": 0, "rationale": "Good work", "satisfaction": "85"},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "'85' is not of type 'integer', in path [0, 'satisfaction']",
        ),
        # Minimum violation: satisfaction below 0
        (
            [
                {"id": 0, "rationale": "Good work", "satisfaction": -1},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "-1 is less than the minimum of 0, in path [0, 'satisfaction']",
        ),
        # Maximum violation: satisfaction above 100
        (
            [
                {"id": 0, "rationale": "Good work", "satisfaction": 101},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 60},
            ],
            "101 is greater than the maximum of 100, in path [0, 'satisfaction']",
        ),
    ]

    for idx, (test_data, expected) in enumerate(tests):
        result = LlmBase.json_validator(test_data, schema)
        assert result == expected, f"---> {idx}"


@patch.object(NoteGrader, "schema_scores")
def test_build_prompts(mock_schema_scores, tmp_files):
    def reset_mocks():
        mock_schema_scores.reset_mock()

    _, _, _, rubric, note = tmp_files
    rubric_objs = RubricCriterion.load_from_json(rubric)
    tested = NoteGrader(rubric_objs, note)
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
    rubric_objs = RubricCriterion.load_from_json(rubric)
    tested = NoteGrader(rubric_objs, note)
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

    settings = MagicMock()

    def reset_mocks():
        mock_run.reset_mock()
        mock_score_datastore.reset_mock()
        mock_generated_note_datastore.reset_mock()
        mock_rubric_datastore.reset_mock()
        mock_experiment_result_datastore.reset_mock()
        mock_helper.reset_mock()
        settings.reset_mock()
        settings.llm_text = VendorKey(vendor="theVendor", api_key="theApiKey")

    reset_mocks()
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
                        text_llm_vendor="theVendor",
                        text_llm_name="theModel2",
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
        mock_helper.settings_reasoning_allowed.side_effect = [settings]
        mock_helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
        mock_score_datastore.return_value.insert.side_effect = [expected]
        settings.llm_text_model.side_effect = ["theModel1", "theModel2"]
        settings.llm_text_temperature.side_effect = [1.37]

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
                    text_llm_vendor="theVendor",
                    text_llm_name="theModel1",
                    temperature=1.37,
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
            call.settings_reasoning_allowed(),
        ]
        assert mock_helper.mock_calls == calls
        calls = [
            call.llm_text_model(),
            call.llm_text_temperature(),
        ]
        if exp_calls:
            calls.append(call.llm_text_model())
        assert settings.mock_calls == calls
        reset_mocks()


@patch.object(NoteGrader, "load_json")
@patch.object(NoteGrader, "run")
def test_grade_and_save2file(mock_run, mock_load_json, tmp_path, capsys):
    tested = NoteGrader

    def reset_mocks():
        mock_run.reset_mock()
        mock_load_json.reset_mock()

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

    tested.grade_and_save2file(rubric_path, note_path, output_path)

    # Verify mock calls in reset_mocks order
    assert mock_run.mock_calls == [call()]
    assert mock_load_json.mock_calls == [call(rubric_path), call(note_path)]

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

    calls_parser = [
        call.add_argument("--rubric", type=Path, help="Path to rubric.json"),
        call.add_argument("--note", type=Path, help="Path to note.json"),
        call.add_argument("--output", type=Path, help="Where to save grading JSON"),
        call.add_argument("--rubric_id", type=int, help="Rubric ID from database"),
        call.add_argument("--generated_note_id", type=int, help="Generated note ID from database"),
        call.add_argument("--experiment_result_id", type=int, default=0, help="Experiment Result ID from database"),
        call.parse_args(),
    ]

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

        assert mock_parser.mock_calls == calls_parser
        calls = [call(description="Grade a note against a rubric.")]
        assert mock_parser_class.mock_calls == calls
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

        calls = calls_parser + [call.error(test_case["expected_error"])]
        assert mock_parser.mock_calls == calls
        calls = [call(description="Grade a note against a rubric.")]
        assert mock_parser_class.mock_calls == calls
        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    reset_mocks()
