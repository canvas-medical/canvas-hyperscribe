import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call, MagicMock

import pytest

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.constants import Constants

from evaluations.case_builders.synthetic_case_orchestrator import SyntheticCaseOrchestrator
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord


@pytest.fixture
def tmp_files(tmp_path):
    example_chart_data = {"medications": [], "allergies": []}
    example_chart_path = tmp_path / "example_chart.json"
    example_chart_path.write_text(json.dumps(example_chart_data))

    output_root = tmp_path / "output"
    output_root.mkdir()

    return example_chart_path, output_root, example_chart_data


@pytest.fixture
def mock_vendor_key():
    return VendorKey(vendor="openai", api_key="test_key")


@pytest.fixture
def sample_case_synthetic_pairs():
    case_record_1 = CaseRecord(
        id=1,
        name="John Doe",
        transcript={"cycle_001": []},
        limited_chart={"medications": []},
        profile="Profile 1",
        validation_status=CaseStatus.GENERATION,
        batch_identifier="",
        tags={},
    )
    synthetic_record_1 = SyntheticCaseRecord(
        case_id=1,
        category="test",
        turn_total=3,
        speaker_sequence=["Clinician", "Patient", "Clinician"],
        clinician_to_patient_turn_ratio=1.0,
        mood="neutral",
        pressure="neutral",
        clinician_style="neutral",
        patient_style="neutral",
        turn_buckets=SyntheticCaseTurnBuckets.SHORT,
        duration=0.0,
        text_llm_vendor="openai",
        text_llm_name=Constants.OPENAI_CHAT_TEXT_O3,
        id=1,
    )
    return [(case_record_1, synthetic_record_1)]


@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticChartGenerator.load_json")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.tempfile.mkdtemp")
def test___init__(mock_mkdtemp, mock_profile_generator_class, mock_load_json, tmp_files, mock_vendor_key):
    def reset_mocks():
        mock_mkdtemp.reset_mock()
        mock_profile_generator_class.reset_mock()
        mock_load_json.reset_mock()
        mock_profile_generator.reset_mock()

    example_chart_path, output_root, example_chart_data = tmp_files
    mock_profile_generator = MagicMock()
    mock_profile_generator_class.side_effect = [mock_profile_generator]
    mock_load_json.side_effect = [example_chart_data]
    mock_mkdtemp.side_effect = ["/tmp/test"]

    tested = SyntheticCaseOrchestrator(mock_vendor_key, "test_category", example_chart_path)

    assert tested.vendor_key == mock_vendor_key
    assert tested.category == "test_category"
    assert tested.example_chart == example_chart_data
    assert tested.profile_generator == mock_profile_generator

    assert mock_load_json.mock_calls == [call(example_chart_path)]
    assert mock_mkdtemp.mock_calls == [call()]
    assert mock_profile_generator_class.mock_calls == [call(vendor_key=mock_vendor_key, output_path=Path("/tmp/test"))]
    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.tempfile.mkdtemp")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticTranscriptGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticChartGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.Line.load_from_json")
def test_generate(
    mock_line_load_from_json,
    mock_chart_generator_class,
    mock_transcript_generator_class,
    mock_profile_generator_class,
    mock_mkdtemp,
    tmp_files,
    mock_vendor_key,
):
    def reset_mocks():
        mock_line_load_from_json.reset_mock()
        mock_chart_generator_class.reset_mock()
        mock_transcript_generator_class.reset_mock()
        mock_profile_generator_class.reset_mock()
        mock_mkdtemp.reset_mock()

    example_chart_path, _, _ = tmp_files

    test_cases = [
        {
            "description": "normal case with single profile",
            "profiles": {"Test Patient": "Test profile"},
            "raw_transcript": ['{"speaker": "Dr", "text": "Hi"}'],
            "line_objects": [{"speaker": "Dr", "text": "Hi"}],
            "expected_results": 1,
            "should_raise": None,
            "verify_final_cycle": True,
        },
        {
            "description": "empty line objects to test current_cycle empty branch",
            "profiles": {"Empty Patient": "Empty profile"},
            "raw_transcript": ['{"speaker": "Dr", "text": "Hi"}'],
            "line_objects": [],
            "expected_results": 1,
            "should_raise": None,
            "verify_empty_transcript": True,
        },
        {
            "description": "TypeError when transcript item becomes list after JSON parsing",
            "profiles": {"Error Patient": "Error profile"},
            "raw_transcript": ['["not", "a", "dict"]'],
            "line_objects": [],
            "expected_results": 0,
            "should_raise": (TypeError, "Turn #1 decoded to list, expected dict"),
        },
        {
            "description": "large transcript that exceeds MAX_CHARACTERS_PER_CYCLE",
            "profiles": {"Large Patient": "Large profile"},
            "raw_transcript": [
                f'{{"speaker": "Doctor", "text": "{"x" * 600}"}}',
                f'{{"speaker": "Patient", "text": "{"x" * 600}"}}',
            ],
            "line_objects": [
                {"speaker": "Doctor", "text": "x" * 600},
                {"speaker": "Patient", "text": "x" * 600},
            ],
            "expected_results": 1,
            "should_raise": None,
            "verify_cycles": True,
        },
        {
            "description": "two small line objects to test final cycle handling",
            "profiles": {"Simple Patient": "Simple profile"},
            "raw_transcript": ['{"speaker": "Dr", "text": "A"}', '{"speaker": "Pt", "text": "B"}'],
            "line_objects": [
                {"speaker": "Dr", "text": "A"},
                {"speaker": "Pt", "text": "B"},
            ],
            "expected_results": 1,
            "should_raise": None,
            "verify_final_cycle": True,
        },
    ]

    for index, test_case in enumerate(test_cases):
        mock_line_load_from_json.reset_mock()
        mock_chart_generator_class.reset_mock()
        mock_transcript_generator_class.reset_mock()
        mock_profile_generator_class.reset_mock()
        mock_mkdtemp.reset_mock()

        # mocks
        mock_profile_generator = MagicMock()
        mock_profile_generator.all_profiles = test_case["profiles"]
        mock_profile_generator_class.return_value = mock_profile_generator

        mock_chart_generator = MagicMock()
        mock_chart_generator_class.side_effect = [mock_chart_generator]
        mock_chart_data = {"medications": ["test_med"]}
        profile_count = len(test_case["profiles"])
        mock_chart_generator.generate_chart_for_profile.side_effect = [mock_chart_data] * profile_count

        mock_transcript_generator = MagicMock()
        mock_transcript_generator_class.side_effect = [mock_transcript_generator]
        mock_specifications = {
            "turn_total": len(test_case["raw_transcript"]),
            "speaker_sequence": "CP",
            "ratio": 1.0,
            "mood": "neutral",
            "pressure": "low",
            "clinician_style": "professional",
            "patient_style": "cooperative",
            "bucket": SyntheticCaseTurnBuckets.SHORT,
        }
        mock_transcript_generator.generate_transcript_for_profile.side_effect = [
            (test_case["raw_transcript"], mock_specifications)
        ] * profile_count

        if test_case["line_objects"]:
            # separate mock objects.
            mock_line_objects = []
            for line_data in test_case["line_objects"]:
                mock_line_obj = MagicMock()
                mock_line_obj.to_json.return_value = line_data
                mock_line_objects.append(mock_line_obj)
            mock_line_load_from_json.return_value = mock_line_objects
        else:
            mock_line_load_from_json.return_value = []

        mock_mkdtemp.side_effect = [f"/tmp/init_{index}", f"/tmp/orchestrator_temp_{index}"]

        tested = SyntheticCaseOrchestrator(
            mock_vendor_key,
            "test_category",
            example_chart_path,
        )

        if test_case["should_raise"]:
            exception_type, exception_message = test_case["should_raise"]
            with pytest.raises(exception_type, match=exception_message):
                tested.generate(1, profile_count)
        else:
            result = tested.generate(1, profile_count)

            # Verify results
            assert len(result) == test_case["expected_results"]

            for case_record, synthetic_record in result:
                assert isinstance(case_record, CaseRecord)
                assert isinstance(synthetic_record, SyntheticCaseRecord)
                assert case_record.validation_status == CaseStatus.GENERATION
                assert synthetic_record.category == "test_category"
                assert synthetic_record.text_llm_vendor == mock_vendor_key.vendor

                if test_case.get("verify_cycles"):
                    assert len(case_record.transcript) >= 2
                    assert "cycle_001" in case_record.transcript
                    assert "cycle_002" in case_record.transcript

                if test_case.get("verify_final_cycle"):
                    assert len(case_record.transcript) == 1
                    assert "cycle_001" in case_record.transcript
                    expected_line_count = len(test_case["line_objects"])
                    assert len(case_record.transcript["cycle_001"]) == expected_line_count

                if test_case.get("verify_empty_transcript"):
                    assert len(case_record.transcript) == 0
                    assert case_record.transcript == {}

            # Verify mock calls for successful cases
            assert mock_profile_generator.generate_batch.mock_calls == [call(1, profile_count)]
            assert mock_chart_generator.generate_chart_for_profile.call_count == profile_count
            assert mock_transcript_generator.generate_transcript_for_profile.call_count == profile_count
            if test_case["line_objects"]:
                assert mock_line_load_from_json.call_count == profile_count

    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation.postgres_credentials")
@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation.settings")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticCaseDatastore")
@patch("evaluations.case_builders.synthetic_case_orchestrator.CaseDatastore")
@patch.object(SyntheticCaseOrchestrator, "generate")
def test_generate_and_save2database(
    mock_generate,
    mock_case_datastore_class,
    mock_synthetic_datastore_class,
    mock_settings,
    mock_postgres_credentials,
    tmp_files,
    mock_vendor_key,
    sample_case_synthetic_pairs,
):
    def reset_mocks():
        mock_generate.reset_mock()
        mock_case_datastore_class.reset_mock()
        mock_synthetic_datastore_class.reset_mock()
        mock_settings.reset_mock()
        mock_postgres_credentials.reset_mock()
        mock_credentials.reset_mock()
        mock_settings_instance.reset_mock()
        mock_case_datastore.reset_mock()
        mock_synthetic_datastore.reset_mock()
        mock_upserted_case.reset_mock()
        mock_upserted_synthetic.reset_mock()

    tested = SyntheticCaseOrchestrator
    example_chart_path, _, _ = tmp_files

    # mocks
    mock_credentials = MagicMock()
    mock_postgres_credentials.side_effect = [mock_credentials]

    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]

    mock_case_datastore = MagicMock()
    mock_synthetic_datastore = MagicMock()
    mock_case_datastore_class.side_effect = [mock_case_datastore]
    mock_synthetic_datastore_class.side_effect = [mock_synthetic_datastore]

    mock_generate.side_effect = [sample_case_synthetic_pairs]
    mock_upserted_case = MagicMock()
    mock_upserted_case.id = 123
    mock_upserted_synthetic = MagicMock()
    mock_upserted_synthetic.id = 456
    mock_case_datastore.upsert.side_effect = [mock_upserted_case]
    mock_synthetic_datastore.upsert.side_effect = [mock_upserted_synthetic]

    result = tested.generate_and_save2database(2, 5, "test_category", example_chart_path)
    expected = [mock_upserted_synthetic]

    assert result == expected
    assert mock_postgres_credentials.mock_calls == [call()]
    assert mock_settings.mock_calls == [call()]
    assert mock_case_datastore_class.mock_calls == [call(mock_credentials)]
    assert mock_synthetic_datastore_class.mock_calls == [call(mock_credentials)]
    assert mock_generate.mock_calls == [call(2, 5)]
    assert mock_case_datastore.upsert.mock_calls == [call(sample_case_synthetic_pairs[0][0])]

    # verify synthetic case record.
    upserted_synthetic_record = mock_synthetic_datastore.upsert.call_args[0][0]
    assert upserted_synthetic_record.case_id == 123
    assert mock_synthetic_datastore.upsert.call_count == 1

    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation.settings")
@patch.object(SyntheticCaseOrchestrator, "generate")
def test_generate_and_save2file(
    mock_generate,
    mock_settings,
    tmp_files,
    mock_vendor_key,
    sample_case_synthetic_pairs,
    capsys,
):
    def reset_mocks():
        mock_generate.reset_mock()
        mock_settings.reset_mock()
        mock_settings_instance.reset_mock()

    tested = SyntheticCaseOrchestrator
    example_chart_path, output_root, _ = tmp_files

    # mock settings + generate
    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]
    mock_generate.side_effect = [sample_case_synthetic_pairs]

    tested.generate_and_save2file(2, 5, "test_category", example_chart_path, output_root)

    # verify calls, file creation/contents, prints.
    assert mock_settings.mock_calls == [call()]
    assert mock_generate.mock_calls == [call(2, 5)]

    case_record, synthetic_record = sample_case_synthetic_pairs[0]
    patient_dir = output_root / case_record.name.replace(" ", "_")
    case_file = patient_dir / "case_1.json"
    synthetic_file = patient_dir / "synthetic_case_1.json"

    assert patient_dir.exists()
    assert case_file.exists()
    assert synthetic_file.exists()

    case_data = json.loads(case_file.read_text())
    synthetic_data = json.loads(synthetic_file.read_text())

    assert case_data["name"] == case_record.name
    assert case_data["validation_status"] == case_record.validation_status.value
    assert synthetic_data["category"] == synthetic_record.category
    assert synthetic_data["turn_buckets"] == synthetic_record.turn_buckets.value

    captured = capsys.readouterr()
    assert f"Wrote {case_file}" in captured.out
    assert f"Wrote {synthetic_file}" in captured.out

    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.argparse.ArgumentParser")
def test_main(mock_parser_class, tmp_files, capsys):
    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    tested = SyntheticCaseOrchestrator
    mock_parser = MagicMock()
    mock_parser_class.side_effect = [mock_parser]

    example_chart_path, output_root, example_chart_data = tmp_files

    test_cases = [
        # Database mode
        {
            "args": Namespace(
                batches=2,
                batch_size=5,
                category="test_category",
                example_chart=example_chart_path,
                mode="db",
                output_root=None,
            ),
            "expected_method": "generate_and_save2database",
        },
        # File mode
        {
            "args": Namespace(
                batches=2,
                batch_size=5,
                category="test_category",
                example_chart=example_chart_path,
                mode="file",
                output_root=output_root,
            ),
            "expected_method": "generate_and_save2file",
        },
    ]

    for test_case in test_cases:
        mock_parser.parse_args.side_effect = [test_case["args"]]

        if test_case["expected_method"] == "generate_and_save2database":
            mock_saved_records = [MagicMock(), MagicMock()]
            with patch.object(tested, "generate_and_save2database") as mock_method:
                mock_method.side_effect = [mock_saved_records]
                tested.main()
                assert mock_method.mock_calls == [
                    call(
                        test_case["args"].batches,
                        test_case["args"].batch_size,
                        test_case["args"].category,
                        test_case["args"].example_chart,
                    )
                ]
                output = capsys.readouterr().out
                assert f"Inserted {len(mock_saved_records)} synthetic_case records." in output

        else:
            with patch.object(tested, "generate_and_save2file") as mock_method:
                tested.main()
                assert mock_method.mock_calls == [
                    call(
                        test_case["args"].batches,
                        test_case["args"].batch_size,
                        test_case["args"].category,
                        test_case["args"].example_chart,
                        test_case["args"].output_root,
                    )
                ]
                output = capsys.readouterr().out
                assert f"Wrote files to {test_case['args'].output_root}" in output

        reset_mocks()
        mock_parser = MagicMock()
        mock_parser_class.side_effect = [mock_parser]

    # test validation error.
    validation_args = Namespace(
        batches=2,
        batch_size=5,
        category="test_category",
        example_chart=example_chart_path,
        mode="file",
        output_root=None,
    )
    mock_parser.parse_args.side_effect = [validation_args]
    mock_parser.error.side_effect = [SystemExit(2)]

    with pytest.raises(SystemExit):
        tested.main()

    assert mock_parser.error.mock_calls == [call("--output-root is required in file mode")]
    reset_mocks()
