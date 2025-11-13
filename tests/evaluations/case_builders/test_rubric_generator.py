import hashlib
import json
from datetime import datetime, UTC, timezone
from unittest.mock import patch, call, MagicMock

import pytest

from evaluations.case_builders.rubric_generator import RubricGenerator
from evaluations.structures.enums.rubric_validation import RubricValidation
from evaluations.structures.records.rubric import Rubric as RubricRecord
from evaluations.structures.rubric_criterion import RubricCriterion
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.model_spec import ModelSpec
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockClass


@pytest.fixture
def tmp_files(tmp_path):
    transcript = {"conversation": [{"speaker": "Doctor", "text": "Hello patient"}]}
    chart = {"medications": [], "allergies": []}
    canvas_context = {"context": "test context"}

    transcript_path = tmp_path / "transcript.json"
    chart_path = tmp_path / "chart.json"
    canvas_context_path = tmp_path / "canvas_context.json"
    output_path = tmp_path / "rubric_output.json"

    transcript_path.write_text(json.dumps(transcript))
    chart_path.write_text(json.dumps(chart))
    canvas_context_path.write_text(json.dumps(canvas_context))

    return transcript_path, chart_path, canvas_context_path, output_path, transcript, chart, canvas_context


def test_load_json(tmp_path):
    tested = RubricGenerator

    test_cases = [{"hello": "world"}, [{"item": "value"}], {"complex": {"nested": ["data"]}}]

    for expected in test_cases:
        path = tmp_path / f"sample_{hash(str(expected))}.json"
        path.write_text(json.dumps(expected))

        result = tested.load_json(path)
        assert result == expected


def test_schema_rubric():
    tested = RubricGenerator()
    schema = tested.schema_rubric()

    schema_hash = hashlib.md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "419ef17a313b4a934ede2a44347ea20b"
    assert schema_hash == expected_hash

    tests = [
        # Valid case
        ([{"criterion": "Accuracy", "weight": 50}], ""),
        # Valid case with multiple items
        ([{"criterion": "Completeness", "weight": 30}, {"criterion": "Clarity", "weight": 20}], ""),
        # Empty array
        ([], "[] should be non-empty"),
        # Additional properties
        (
            [{"criterion": "Accuracy", "weight": 50, "extra": "field"}],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        # Missing criterion
        ([{"weight": 50}], "'criterion' is a required property, in path [0]"),
        # Missing weight
        ([{"criterion": "Accuracy"}], "'weight' is a required property, in path [0]"),
        # Weight below minimum
        ([{"criterion": "Accuracy", "weight": -1}], "-1 is less than the minimum of 0, in path [0, 'weight']"),
        # Weight above maximum
        ([{"criterion": "Accuracy", "weight": 101}], "101 is greater than the maximum of 100, in path [0, 'weight']"),
    ]

    for idx, (test_data, expected) in enumerate(tests):
        result = LlmBase.json_validator(test_data, schema)
        assert result == expected, f"---> {idx}"


@patch.object(RubricGenerator, "schema_rubric")
def test_build_prompts(mock_schema_rubric, tmp_files):
    def reset_mocks():
        mock_schema_rubric.reset_mock()

    _, _, _, _, transcript, chart, canvas_context = tmp_files
    tested = RubricGenerator()
    expected_schema = {"type": "array"}
    mock_schema_rubric.side_effect = [expected_schema]

    result_system_lines, result_user_lines = tested.build_prompts(transcript, chart, canvas_context)
    expected_system_prompt_md5 = "a32a64e63443ef0f076080b5be3873d9"
    expected_user_prompt_md5 = "f93ef0d3dbba3415884f3b9af0ee1d5c"

    result_system_prompt_md5 = hashlib.md5("\n".join(result_system_lines).encode()).hexdigest()
    result_user_prompt_md5 = hashlib.md5("\n".join(result_user_lines).encode()).hexdigest()

    assert result_system_prompt_md5 == expected_system_prompt_md5
    assert result_user_prompt_md5 == expected_user_prompt_md5
    assert mock_schema_rubric.mock_calls == [call()]
    reset_mocks()


@patch.object(RubricGenerator, "build_prompts")
@patch.object(RubricGenerator, "schema_rubric")
@patch("evaluations.case_builders.rubric_generator.HelperSyntheticJson.generate_json")
def test_generate(mock_generate_json, mock_schema_rubric, mock_build_prompts, tmp_files):
    def reset_mocks():
        mock_generate_json.reset_mock()
        mock_schema_rubric.reset_mock()
        mock_build_prompts.reset_mock()

    _, _, _, _, transcript, chart, canvas_context = tmp_files
    tested = RubricGenerator()
    expected_schema = {"type": "array"}

    test_cases = [
        # success case
        {
            "generate_json_response": [
                RubricCriterion(criterion="Reward for completeness", weight=50),
                RubricCriterion(criterion="Reward for accuracy", weight=30),
            ],
            "expected": [
                RubricCriterion(criterion="Reward for completeness", weight=50),
                RubricCriterion(criterion="Reward for accuracy", weight=30),
            ],
        },
        # different rubric case
        {
            "generate_json_response": [
                RubricCriterion(criterion="Reward for chart integration", weight=40),
            ],
            "expected": [
                RubricCriterion(criterion="Reward for chart integration", weight=40),
            ],
        },
    ]

    for test_case in test_cases:
        mock_build_prompts.side_effect = [(["System Prompt"], ["User Prompt"])]
        mock_schema_rubric.side_effect = [expected_schema]
        mock_generate_json.side_effect = [test_case["generate_json_response"]]

        result = tested.generate(transcript, chart, canvas_context)
        expected = test_case["expected"]
        assert result == expected

        calls = [call()]
        assert mock_schema_rubric.mock_calls == calls
        assert mock_build_prompts.mock_calls == [call(transcript, chart, canvas_context)]

        expected_call = [
            call(
                system_prompt=["System Prompt"],
                user_prompt=["User Prompt"],
                schema=expected_schema,
                returned_class=RubricCriterion,
            )
        ]
        assert mock_generate_json.mock_calls == expected_call
        reset_mocks()

    # test exception case
    mock_build_prompts.side_effect = [(["System Prompt"], ["User Prompt"])]
    mock_schema_rubric.side_effect = [expected_schema]
    mock_generate_json.side_effect = [SystemExit(1)]

    with pytest.raises(SystemExit) as exc_info:
        tested.generate(transcript, chart, canvas_context)

    assert exc_info.value.code == 1
    assert mock_schema_rubric.mock_calls == [call()]
    assert mock_build_prompts.mock_calls == [call(transcript, chart, canvas_context)]
    expected_call = [
        call(
            system_prompt=["System Prompt"],
            user_prompt=["User Prompt"],
            schema=expected_schema,
            returned_class=RubricCriterion,
        )
    ]
    assert mock_generate_json.mock_calls == expected_call
    reset_mocks()


@patch.object(RubricGenerator, "load_json")
@patch.object(RubricGenerator, "generate")
def test_generate_and_save2file(mock_generate, mock_load_json, tmp_files, capsys):
    tested = RubricGenerator

    def reset_mocks():
        mock_generate.reset_mock()
        mock_load_json.reset_mock()

    transcript_path, chart_path, canvas_context_path, output_path, transcript, chart, canvas_context = tmp_files

    rubric_result = [RubricCriterion(criterion="Reward for accuracy", weight=60)]

    mock_load_json.side_effect = [transcript, chart, canvas_context]
    mock_generate.side_effect = [rubric_result]

    tested.generate_and_save2file(transcript_path, chart_path, canvas_context_path, output_path)

    assert mock_generate.mock_calls == [call(transcript, chart, canvas_context)]
    assert mock_load_json.mock_calls == [call(transcript_path), call(chart_path), call(canvas_context_path)]

    assert output_path.exists()
    result = json.loads(output_path.read_text())
    expected = [{"criterion": "Reward for accuracy", "weight": 60}]
    assert result == expected

    output = capsys.readouterr().out
    assert f"Saved rubric to file at: {output_path}" in output

    reset_mocks()


@patch("evaluations.case_builders.rubric_generator.datetime", wraps=datetime)
@patch("evaluations.case_builders.rubric_generator.HelperEvaluation")
@patch("evaluations.case_builders.rubric_generator.RubricDatastore")
@patch("evaluations.case_builders.rubric_generator.CaseDatastore")
@patch.object(RubricGenerator, "load_json")
@patch.object(RubricGenerator, "generate")
def test_generate_and_save2database(
    mock_generate,
    mock_load_json,
    mock_case_datastore_class,
    mock_rubric_datastore_class,
    mock_helper,
    mock_datetime,
    tmp_files,
):
    tested = RubricGenerator
    settings = MagicMock()

    def reset_mocks():
        mock_generate.reset_mock()
        mock_load_json.reset_mock()
        mock_case_datastore_class.reset_mock()
        mock_rubric_datastore_class.reset_mock()
        mock_helper.reset_mock()
        mock_datetime.reset_mock()
        settings.reset_mock()
        settings.llm_text = VendorKey(vendor="theVendor", api_key="theApiKey")

    reset_mocks()

    _, _, canvas_context_path, _, _, _, canvas_context = tmp_files
    case_name = "test_case"
    case_id = 123
    transcript_data = {"conversation": "test"}
    chart_data = {"data": "test"}
    rubric_result = [RubricCriterion(criterion="Test", weight=50)]
    date_0 = datetime(2025, 10, 20, 11, 16, 24, 123456, tzinfo=timezone.utc)

    mock_case_datastore_class.return_value.get_id.side_effect = [case_id]
    mock_case_datastore_class.return_value.get_transcript.side_effect = [transcript_data]
    mock_case_datastore_class.return_value.get_limited_chart.side_effect = [chart_data]
    mock_load_json.side_effect = [canvas_context]
    mock_generate.side_effect = [rubric_result]
    mock_helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    mock_helper.settings_reasoning_allowed.side_effect = [settings]
    mock_rubric_datastore_class.return_value.insert.side_effect = ["theInsertedRecord"]
    mock_datetime.now.side_effect = [date_0]
    settings.llm_text_model.side_effect = ["theModel"]
    settings.llm_text_temperature.side_effect = [1.37]

    result = tested.generate_and_save2database(case_name, canvas_context_path)
    expected = "theInsertedRecord"
    assert result == expected

    calls = [call(transcript_data, chart_data, canvas_context)]
    assert mock_generate.mock_calls == calls
    calls = [call(canvas_context_path)]
    assert mock_load_json.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_id(case_name),
        call().get_transcript(case_id),
        call().get_limited_chart(case_id),
    ]
    assert mock_case_datastore_class.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().insert(
            RubricRecord(
                case_id=case_id,
                parent_rubric_id=None,
                validation_timestamp=date_0,
                validation=RubricValidation.NOT_EVALUATED,
                author="llm",
                rubric=[{"criterion": "Test", "weight": 50}],
                case_provenance_classification="",
                comments="",
                text_llm_vendor="theVendor",
                text_llm_name="theModel",
                temperature=1.37,
                id=0,
            )
        ),
    ]
    assert mock_rubric_datastore_class.mock_calls == calls
    calls = [
        call.settings_reasoning_allowed(),
        call.postgres_credentials(),
    ]
    assert mock_helper.mock_calls == calls
    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    calls = [
        call.llm_text_model(ModelSpec.LISTED),
        call.llm_text_temperature(),
    ]
    assert settings.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.rubric_generator.argparse.ArgumentParser")
def test_main(mock_parser_class, tmp_files, capsys):
    tested = RubricGenerator
    mock_parser = MagicMock()

    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    mock_parser_class.side_effect = [mock_parser]

    transcript_path, chart_path, canvas_context_path, output_path, _, _, _ = tmp_files

    test_cases = [
        # File mode
        {
            "args": MockClass(
                transcript_path=transcript_path,
                chart_path=chart_path,
                canvas_context_path=canvas_context_path,
                output_path=output_path,
                case_name=None,
            ),
            "expected_method": "generate_and_save2file",
        },
        # Database mode
        {
            "args": MockClass(
                transcript_path=None,
                chart_path=None,
                canvas_context_path=canvas_context_path,
                output_path=None,
                case_name="test_case",
            ),
            "expected_method": "generate_and_save2database",
        },
    ]

    for test_case in test_cases:
        mock_parser.parse_args.side_effect = [test_case["args"]]

        if test_case["expected_method"] == "generate_and_save2file":
            with patch.object(tested, "generate_and_save2file") as mock_method:
                tested.main()
                assert mock_method.mock_calls == [
                    call(
                        test_case["args"].transcript_path,
                        test_case["args"].chart_path,
                        test_case["args"].canvas_context_path,
                        test_case["args"].output_path,
                    )
                ]
        else:
            mock_rubric_record = MagicMock()
            mock_rubric_record.id = 789
            with patch.object(tested, "generate_and_save2database") as mock_method:
                mock_method.side_effect = [mock_rubric_record]
                tested.main()
                assert mock_method.mock_calls == [
                    call(test_case["args"].case_name, test_case["args"].canvas_context_path)
                ]
                output = capsys.readouterr().out
                assert f"Saved rubric to database with ID: {mock_rubric_record.id}" in output

        assert mock_parser_class.mock_calls == [call(description="Generate a fidelity rubric for documentation.")]
        assert mock_parser.parse_args.mock_calls == [call()]

        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    # Test parameter validation cases
    validation_test_cases = [
        # Missing parameters
        {
            "args": MockClass(
                transcript_path=None,
                chart_path=None,
                canvas_context_path=None,
                output_path=None,
                case_name=None,
            ),
            "expected_error": "Must provide either all file inputs or (--case_name and --canvas_context_path).",
        },
        # Conflicting parameters
        {
            "args": MockClass(
                transcript_path=transcript_path,
                chart_path=chart_path,
                canvas_context_path=canvas_context_path,
                output_path=output_path,
                case_name="test_case",
            ),
            "expected_error": "Cannot mix file-based and DB-based generation modes.",
        },
    ]

    for test_case in validation_test_cases:
        mock_parser.parse_args.side_effect = [test_case["args"]]
        mock_parser.error.side_effect = [SystemExit(2)]

        with pytest.raises(SystemExit):
            tested.main()

        assert mock_parser_class.mock_calls == [call(description="Generate a fidelity rubric for documentation.")]
        assert mock_parser.parse_args.mock_calls == [call()]
        assert mock_parser.error.mock_calls == [call(test_case["expected_error"])]
        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    reset_mocks()
