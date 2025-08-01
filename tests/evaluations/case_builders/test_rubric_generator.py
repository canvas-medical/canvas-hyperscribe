import hashlib
import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock
from datetime import datetime

import pytest

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.constants import Constants as HyperscribeConstants

from evaluations.case_builders.rubric_generator import RubricGenerator
from evaluations.structures.enums.rubric_validation import RubricValidation


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
    tested = RubricGenerator(VendorKey("openai", "KEY"))

    result = tested.schema_rubric()
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "criterion": {
                    "type": "string",
                    "description": "dimension of note being evaluated",
                },
                "weight": {
                    "type": "integer",
                    "description": "how much criterion is worth",
                    "minimum": 0,
                    "maximum": 100,
                },
                "sense": {
                    "type": "string",
                    "description": "positive or negative direction",
                    "enum": ["positive", "negative"],
                },
            },
            "required": ["criterion", "weight", "sense"],
            "additionalProperties": False,
        },
    }

    assert result == expected


@patch.object(RubricGenerator, "schema_rubric")
def test_build_prompts(mock_schema_rubric, tmp_files):
    def reset_mocks():
        mock_schema_rubric.reset_mock()

    _, _, _, _, transcript, chart, canvas_context = tmp_files
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    tested = RubricGenerator(vendor_key)
    expected_schema = {"type": "array"}
    mock_schema_rubric.side_effect = [expected_schema]

    result_system_lines, result_user_lines = tested.build_prompts(transcript, chart, canvas_context)
    expected_system_md5 = "a32a64e63443ef0f076080b5be3873d9"
    expected_user_md5 = "f08e7813044d358e28018de214b8a512"

    result_system_md5 = hashlib.md5("\n".join(result_system_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(result_user_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
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
    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    tested = RubricGenerator(vendor_key)
    expected_schema = {"type": "array"}

    test_cases = [
        # success case
        {
            "generate_json_response": [
                {"criterion": "Reward for completeness", "weight": 50, "sense": "positive"},
                {"criterion": "Penalize for inaccuracy", "weight": 30, "sense": "negative"},
            ],
            "expected": [
                {"criterion": "Reward for completeness", "weight": 50, "sense": "positive"},
                {"criterion": "Penalize for inaccuracy", "weight": 30, "sense": "negative"},
            ],
        },
        # different rubric case
        {
            "generate_json_response": [
                {"criterion": "Reward for chart integration", "weight": 40, "sense": "positive"},
            ],
            "expected": [
                {"criterion": "Reward for chart integration", "weight": 40, "sense": "positive"},
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
    mock_schema_rubric.side_effect = [expected_schema]
    mock_generate_json.side_effect = [SystemExit(1)]

    with pytest.raises(SystemExit) as exc_info:
        tested.generate(transcript, chart, canvas_context)

    assert exc_info.value.code == 1
    assert mock_schema_rubric.mock_calls == [call()]
    assert mock_build_prompts.mock_calls == [call(transcript, chart, canvas_context)]
    assert mock_generate_json.call_count == 1
    reset_mocks()


@patch("evaluations.case_builders.rubric_generator.HelperEvaluation.settings")
@patch.object(RubricGenerator, "load_json")
@patch.object(RubricGenerator, "generate")
def test_generate_and_save2file(mock_generate, mock_load_json, mock_settings, tmp_files, capsys):
    def reset_mocks():
        mock_generate.reset_mock()
        mock_load_json.reset_mock()
        mock_settings.reset_mock()
        mock_settings_instance.reset_mock()

    tested = RubricGenerator

    # mock settings and data.
    mock_vendor_key = VendorKey(vendor="openai", api_key="test_key")
    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]

    transcript_path, chart_path, canvas_context_path, output_path, transcript, chart, canvas_context = tmp_files

    rubric_result = [{"criterion": "Reward for accuracy", "weight": 60, "sense": "positive"}]

    mock_load_json.side_effect = [transcript, chart, canvas_context]
    mock_generate.side_effect = [rubric_result]

    # call method for testing.
    tested.generate_and_save2file(transcript_path, chart_path, canvas_context_path, output_path)

    # verify calls, output files, and print.
    assert mock_settings.mock_calls == [call()]
    assert mock_load_json.mock_calls == [call(transcript_path), call(chart_path), call(canvas_context_path)]
    assert mock_generate.mock_calls == [call(transcript, chart, canvas_context)]

    assert output_path.exists()
    result = json.loads(output_path.read_text())
    expected = rubric_result
    assert result == expected

    output = capsys.readouterr().out
    assert f"Saved rubric to file at: {output_path}" in output

    reset_mocks()


@patch("evaluations.case_builders.rubric_generator.datetime", wraps=datetime)
@patch("evaluations.case_builders.rubric_generator.HelperEvaluation.postgres_credentials")
@patch("evaluations.case_builders.rubric_generator.HelperEvaluation.settings")
@patch.object(RubricGenerator, "load_json")
@patch.object(RubricGenerator, "generate")
@patch("evaluations.case_builders.rubric_generator.RubricDatastore")
@patch("evaluations.case_builders.rubric_generator.CaseDatastore")
def test_generate_and_save2database(
    mock_case_ds_class,
    mock_rubric_ds_class,
    mock_generate,
    mock_load_json,
    mock_settings,
    mock_postgres_credentials,
    mock_datetime,
    tmp_files,
):
    def reset_mocks():
        mock_case_ds_class.reset_mock()
        mock_rubric_ds_class.reset_mock()
        mock_generate.reset_mock()
        mock_load_json.reset_mock()
        mock_settings.reset_mock()
        mock_postgres_credentials.reset_mock()
        mock_datetime.reset_mock()
        mock_credentials.reset_mock()
        mock_case_ds.reset_mock()
        mock_rubric_ds.reset_mock()
        mock_rubric_record.reset_mock()

    tested = RubricGenerator

    # mock credentials, settings, datastores, canvas data.
    mock_credentials = MagicMock()
    mock_postgres_credentials.side_effect = [mock_credentials]

    mock_vendor_key = VendorKey(vendor="openai", api_key="test_key")
    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]

    mock_case_ds = MagicMock()
    mock_rubric_ds = MagicMock()
    mock_case_ds_class.side_effect = [mock_case_ds]
    mock_rubric_ds_class.side_effect = [mock_rubric_ds]

    _, _, canvas_context_path, _, _, _, canvas_context = tmp_files
    case_name = "test_case"
    case_id = 123
    transcript_data = {"conversation": "test"}
    chart_data = {"data": "test"}
    rubric_result = [{"criterion": "Test", "weight": 50, "sense": "positive"}]

    mock_case_ds.get_id.side_effect = [case_id]
    mock_case_ds.get_transcript.side_effect = [transcript_data]
    mock_case_ds.get_limited_chart.side_effect = [chart_data]
    mock_load_json.side_effect = [canvas_context]
    mock_generate.side_effect = [rubric_result]

    mock_rubric_record = MagicMock()
    mock_rubric_record.id = 789
    mock_rubric_ds.upsert.side_effect = [mock_rubric_record]

    result = tested.generate_and_save2database(case_name, canvas_context_path)
    expected = mock_rubric_record

    assert result == expected

    # verify calls + rubric_record.
    assert mock_postgres_credentials.mock_calls == [call()]
    assert mock_settings.mock_calls == [call()]
    assert mock_case_ds_class.mock_calls == [call(mock_credentials)]
    assert mock_rubric_ds_class.mock_calls == [call(mock_credentials)]
    assert mock_case_ds.get_id.mock_calls == [call(case_name)]
    assert mock_case_ds.get_transcript.mock_calls == [call(case_id)]
    assert mock_case_ds.get_limited_chart.mock_calls == [call(case_id)]
    assert mock_load_json.mock_calls == [call(canvas_context_path)]
    assert mock_generate.mock_calls == [call(transcript_data, chart_data, canvas_context)]

    assert mock_rubric_ds.upsert.call_count == 1
    rubric_record_arg = mock_rubric_ds.upsert.call_args[0][0]
    assert rubric_record_arg.case_id == case_id
    assert rubric_record_arg.rubric == rubric_result
    assert rubric_record_arg.text_llm_vendor == "openai"
    assert rubric_record_arg.text_llm_name == HyperscribeConstants.OPENAI_CHAT_TEXT_O3
    assert rubric_record_arg.validation == RubricValidation.NOT_EVALUATED

    reset_mocks()


@patch("evaluations.case_builders.rubric_generator.argparse.ArgumentParser")
def test_main(mock_parser_class, tmp_files, capsys):
    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    tested = RubricGenerator
    mock_parser = MagicMock()
    mock_parser_class.side_effect = [mock_parser]

    transcript_path, chart_path, canvas_context_path, output_path, _, _, _ = tmp_files

    test_cases = [
        # File mode
        {
            "args": Namespace(
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
            "args": Namespace(
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

        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    # Test parameter validation cases
    validation_test_cases = [
        # Missing parameters
        {
            "args": Namespace(
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
            "args": Namespace(
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

        assert mock_parser.error.mock_calls == [call(test_case["expected_error"])]
        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    reset_mocks()
