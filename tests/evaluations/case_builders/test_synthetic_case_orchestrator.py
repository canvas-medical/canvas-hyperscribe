import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

import pytest

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.constants import Constants

from evaluations.case_builders.synthetic_case_orchestrator import SyntheticCaseOrchestrator
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord
from evaluations.structures.specification import Specification
from hyperscribe.structures.line import Line
from evaluations.structures.chart import Chart
from evaluations.structures.patient_profile import PatientProfile


@pytest.fixture
def tmp_files(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    return output_root


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
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        turn_buckets=SyntheticCaseTurnBuckets.SHORT,
        duration=0.0,
        text_llm_vendor="openai",
        text_llm_name=Constants.OPENAI_CHAT_TEXT_O3,
        id=1,
    )
    return [(case_record_1, synthetic_record_1)]


@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
def test___init__(mock_profile_generator_class, tmp_files, mock_vendor_key):
    mock_profile_generator = MagicMock()
    mock_profile_generator_class.side_effect = [mock_profile_generator]

    def reset_mocks():
        mock_profile_generator_class.reset_mock()
        mock_profile_generator.reset_mock()

    tested = SyntheticCaseOrchestrator(mock_vendor_key, "test_category")

    assert tested.vendor_key == mock_vendor_key
    assert tested.category == "test_category"
    assert tested.profile_generator == mock_profile_generator

    assert mock_profile_generator_class.mock_calls == [call(vendor_key=mock_vendor_key)]
    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation.split_lines_into_cycles")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticTranscriptGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticChartGenerator")
def test_generate(
    mock_chart_generator_class,
    mock_transcript_generator_class,
    mock_profile_generator_class,
    mock_split_lines_into_cycles,
    mock_vendor_key,
):
    def reset_mocks():
        mock_chart_generator_class.reset_mock()
        mock_transcript_generator_class.reset_mock()
        mock_profile_generator_class.reset_mock()
        mock_split_lines_into_cycles.reset_mock()

    test_cases = [
        {
            "description": "normal case with single profile",
            "profiles": {"Test Patient": "Test profile"},
            "line_objects": [{"speaker": "Dr", "text": "Hi"}],
            "expected_results": 1,
        },
        {
            "description": "multiple profiles",
            "profiles": {"Patient A": "Profile A", "Patient B": "Profile B"},
            "line_objects": [{"speaker": "Dr", "text": "Hello"}],
            "expected_results": 2,
        },
    ]

    for index, test_case in enumerate(test_cases):
        # mocks
        mock_profile_generator = MagicMock()
        # Convert profiles dict to list[PatientProfile] for generate_batch return
        profiles_list = [PatientProfile(name=name, profile=profile) for name, profile in test_case["profiles"].items()]
        mock_profile_generator.generate_batch.side_effect = [profiles_list]
        mock_profile_generator_class.return_value = mock_profile_generator

        mock_chart_generator = MagicMock()
        mock_chart_generator_class.side_effect = [mock_chart_generator]
        # Create Chart instances for the mock return
        mock_chart = Chart(
            demographic_str="Test patient",
            condition_history="Test conditions",
            current_allergies="None",
            current_conditions="None",
            current_medications="test_med",
            current_goals="Test goals",
            family_history="None",
            surgery_history="None",
        )
        profile_count = len(test_case["profiles"])
        mock_chart_generator.generate_chart_for_profile.side_effect = [mock_chart] * profile_count

        mock_transcript_generator = MagicMock()
        mock_transcript_generator_class.side_effect = [mock_transcript_generator]
        mock_specifications = Specification(
            turn_total=len(test_case["line_objects"]),
            speaker_sequence=["Clinician", "Patient"],
            ratio=1.0,
            mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
            pressure=SyntheticCasePressure.TIME_PRESSURE,
            clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
            patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
            bucket=SyntheticCaseTurnBuckets.SHORT,
        )
        # Create Line objects for the transcript
        mock_line_objects = []
        for line_data in test_case["line_objects"]:
            mock_line = MagicMock(spec=Line)
            mock_line.speaker = line_data["speaker"]
            mock_line.text = line_data["text"]
            mock_line_objects.append(mock_line)

        mock_transcript_generator.generate_transcript_for_profile.side_effect = [
            (mock_line_objects, mock_specifications)
        ] * profile_count

        # Mock the split_lines_into_cycles method with controlled cycle key
        expected_cycle_key = "test_cycle_001"
        mock_transcript_cycles = {expected_cycle_key: mock_line_objects}
        mock_split_lines_into_cycles.side_effect = [mock_transcript_cycles] * profile_count

        tested = SyntheticCaseOrchestrator(
            mock_vendor_key,
            "test_category",
        )

        with patch.object(Constants, "OPENAI_CHAT_TEXT_O3", "test_model_name"):
            result = tested.generate(1, profile_count)

        # Verify results
        assert len(result) == test_case["expected_results"]

        for case_record, synthetic_record in result:
            assert isinstance(case_record, CaseRecord)
            assert isinstance(synthetic_record, SyntheticCaseRecord)
            assert case_record.validation_status == CaseStatus.GENERATION
            assert synthetic_record.category == "test_category"
            assert synthetic_record.text_llm_vendor == mock_vendor_key.vendor

            # Verify transcript structure
            if test_case["line_objects"]:
                assert len(case_record.transcript) == 1
                assert expected_cycle_key in case_record.transcript
                expected_line_count = len(test_case["line_objects"])
                assert len(case_record.transcript[expected_cycle_key]) == expected_line_count
                assert case_record.transcript == mock_transcript_cycles

        # Verify mock calls
        assert mock_profile_generator.generate_batch.mock_calls == [call(1, profile_count)]
        assert mock_chart_generator.generate_chart_for_profile.call_count == profile_count
        assert mock_transcript_generator.generate_transcript_for_profile.call_count == profile_count
        if test_case["line_objects"]:
            assert mock_split_lines_into_cycles.call_count == profile_count

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
    mock_vendor_key,
    sample_case_synthetic_pairs,
):
    tested = SyntheticCaseOrchestrator

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

    result = tested.generate_and_save2database(2, 5, "test_category")
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
    tested = SyntheticCaseOrchestrator
    output_root = tmp_files

    # mock settings + generate
    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = mock_vendor_key
    mock_settings.side_effect = [mock_settings_instance]
    mock_generate.side_effect = [sample_case_synthetic_pairs]

    def reset_mocks():
        mock_generate.reset_mock()
        mock_settings.reset_mock()
        mock_settings_instance.reset_mock()

    tested.generate_and_save2file(2, 5, "test_category", output_root)

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
    assert case_data["validationStatus"] == case_record.validation_status.value
    assert synthetic_data["category"] == synthetic_record.category
    assert synthetic_data["turn_buckets"] == synthetic_record.turn_buckets.value

    captured = capsys.readouterr()
    assert f"Wrote {case_file}" in captured.out
    assert f"Wrote {synthetic_file}" in captured.out

    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.argparse.ArgumentParser")
def test_main(mock_parser_class, tmp_files, capsys):
    tested = SyntheticCaseOrchestrator
    mock_parser = MagicMock()
    mock_parser_class.side_effect = [mock_parser]

    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    output_root = tmp_files

    test_cases = [
        # Database mode
        {
            "args": Namespace(
                batches=2,
                batch_size=5,
                category="test_category",
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
        mode="file",
        output_root=None,
    )
    mock_parser.parse_args.side_effect = [validation_args]
    mock_parser.error.side_effect = [SystemExit(2)]

    with pytest.raises(SystemExit):
        tested.main()

    assert mock_parser.error.mock_calls == [call("--output-root is required in file mode")]
    reset_mocks()
