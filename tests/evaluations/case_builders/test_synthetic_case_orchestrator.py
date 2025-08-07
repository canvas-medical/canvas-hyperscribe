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
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord
from evaluations.structures.specification import Specification
from hyperscribe.structures.line import Line
from evaluations.structures.chart import Chart
from evaluations.structures.chart_item import ChartItem
from evaluations.structures.patient_profile import PatientProfile


@pytest.fixture
def tmp_files(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    return output_root


@pytest.fixture
def vendor_key_instance():
    return VendorKey(vendor="openai", api_key="test_key")


@pytest.fixture
def sample_case_synthetic_pairs():
    case_record = CaseRecord(
        id=1,
        name="John Doe",
        transcript={"cycle_001": []},
        limited_chart={"medications": []},
        profile="Profile 1",
        validation_status=CaseStatus.GENERATION,
        batch_identifier="",
        tags={},
    )
    synthetic_record = SyntheticCaseRecord(
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
    return [(case_record, synthetic_record)]


@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
def test___init__(mock_profile_generator_class, tmp_files, vendor_key_instance):
    mock_profile_generator = MagicMock()
    mock_profile_generator_class.side_effect = [mock_profile_generator]

    def reset_mocks():
        mock_profile_generator_class.reset_mock()
        mock_profile_generator.reset_mock()

    tested = SyntheticCaseOrchestrator(vendor_key_instance, "test_category")

    assert tested.vendor_key == vendor_key_instance
    assert tested.category == "test_category"
    assert tested.profile_generator == mock_profile_generator
    assert mock_profile_generator_class.mock_calls == [call(vendor_key=vendor_key_instance)]
    reset_mocks()


@pytest.mark.parametrize(
    "profiles,line_objects,expected_count",
    [
        ({"Test Patient": "Profile A"}, [{"speaker": "Clinician", "text": "Hi"}], 1),
        ({"A": "P1", "B": "P2"}, [{"speaker": "Clinician", "text": "Hello"}], 2),
    ],
)
@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation.split_lines_into_cycles")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticTranscriptGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticChartGenerator")
def test_generate(
    mock_chart_generator_class,
    mock_transcript_generator_class,
    mock_profile_generator_class,
    mock_split_cycles,
    vendor_key_instance,
    profiles,
    line_objects,
    expected_count,
):
    def reset_mocks():
        mock_profile_generator_class.reset_mock()
        mock_transcript_generator_class.reset_mock()
        mock_chart_generator_class.reset_mock()
        mock_split_cycles.reset_mock()
        mock_profile_generator.reset_mock()
        mock_transcript_generator.reset_mock()
        mock_chart_generator.reset_mock()

    mock_profile_generator = MagicMock()
    mock_transcript_generator = MagicMock()
    mock_chart_generator = MagicMock()

    profiles_dict = profiles if isinstance(profiles, dict) else dict([profiles])
    profiles_list = [PatientProfile(name=n, profile=p) for n, p in profiles_dict.items()]
    mock_profile_generator.generate_batch.side_effect = [profiles_list]
    mock_profile_generator_class.side_effect = [mock_profile_generator]

    chart = Chart(
        demographic_str="Demo",
        condition_history=[ChartItem(code="Z87.891", label="Personal history", uuid="uuid-1")],
        current_allergies=[],
        current_conditions=[ChartItem(code="J45.9", label="Test condition", uuid="uuid-2")],
        current_medications=[ChartItem(code="329498", label="Test medication", uuid="uuid-3")],
        current_goals=[ChartItem(code="", label="Test goal", uuid="uuid-4")],
        family_history=[],
        surgery_history=[],
    )
    mock_chart_generator.generate_chart_for_profile.side_effect = [chart] * len(profiles_list)
    mock_chart_generator_class.side_effect = [mock_chart_generator]

    lines = []
    for data in line_objects:
        line = MagicMock(spec=Line)
        line.speaker = data["speaker"]
        line.text = data["text"]
        lines.append(line)
    specifications = Specification(
        turn_total=len(line_objects),
        speaker_sequence=["Clinician", "Patient"],
        ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )
    mock_transcript_generator.generate_transcript_for_profile.side_effect = [(lines, specifications)] * len(
        profiles_list
    )
    mock_transcript_generator_class.side_effect = [mock_transcript_generator]

    cycle_key = "cycle_001"
    mock_split_cycles.side_effect = [{cycle_key: lines}] * len(profiles_list)

    tested = SyntheticCaseOrchestrator(vendor_key_instance, "test_cat")
    with patch("evaluations.case_builders.synthetic_case_orchestrator.Constants.OPENAI_CHAT_TEXT_O3", "model_x"):
        result = tested.generate(batches=1, batch_size=len(profiles_list))
    expected = expected_count

    assert len(result) == expected
    for case_record, synthetic_case_record in result:
        assert isinstance(case_record, CaseRecord)
        assert isinstance(synthetic_case_record, SyntheticCaseRecord)
        assert case_record.validation_status == CaseStatus.GENERATION
        assert synthetic_case_record.category == "test_cat"
        assert synthetic_case_record.text_llm_vendor == vendor_key_instance.vendor

    assert mock_profile_generator_class.mock_calls == [call(vendor_key=vendor_key_instance)]
    assert mock_profile_generator.generate_batch.mock_calls == [call(1, len(profiles_list))]
    assert mock_chart_generator_class.mock_calls == [call(vendor_key=vendor_key_instance, profiles=profiles_list)]
    calls = [call(p) for p in profiles_list]
    assert mock_chart_generator.generate_chart_for_profile.mock_calls == calls
    assert mock_transcript_generator.generate_transcript_for_profile.mock_calls == calls
    assert mock_transcript_generator_class.mock_calls == [call(vendor_key=vendor_key_instance, profiles=profiles_list)]
    assert mock_split_cycles.mock_calls == [call(lines)] * len(profiles_list)

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
    vendor_key_instance,
    sample_case_synthetic_pairs,
):
    tested = SyntheticCaseOrchestrator

    # mocks
    mock_credentials = MagicMock()
    mock_postgres_credentials.side_effect = [mock_credentials]

    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = vendor_key_instance
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

    assert mock_generate.mock_calls == [call(2, 5)]
    assert mock_case_datastore_class.mock_calls == [call(mock_credentials)]
    assert mock_synthetic_datastore_class.mock_calls == [call(mock_credentials)]
    assert mock_settings.mock_calls == [call()]
    assert mock_postgres_credentials.mock_calls == [call()]
    assert mock_credentials.mock_calls == []
    assert mock_settings_instance.mock_calls == []
    assert mock_case_datastore.mock_calls == [call.upsert(sample_case_synthetic_pairs[0][0])]
    assert mock_synthetic_datastore.mock_calls == [
        call.upsert(
            SyntheticCaseRecord(
                case_id=123,
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
                text_llm_name="o3",
                id=1,
            )
        )
    ]
    assert mock_upserted_case.mock_calls == []
    assert mock_upserted_synthetic.mock_calls == []

    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation.settings")
@patch.object(SyntheticCaseOrchestrator, "generate")
def test_generate_and_save2file(
    mock_generate,
    mock_settings,
    tmp_files,
    vendor_key_instance,
    sample_case_synthetic_pairs,
    capsys,
):
    tested = SyntheticCaseOrchestrator
    output_root = tmp_files

    mock_settings_instance = MagicMock()
    mock_settings_instance.llm_text = vendor_key_instance
    mock_settings.side_effect = [mock_settings_instance]
    mock_generate.side_effect = [sample_case_synthetic_pairs]

    def reset_mocks():
        mock_generate.reset_mock()
        mock_settings.reset_mock()
        mock_settings_instance.reset_mock()

    tested.generate_and_save2file(2, 5, "test_category", output_root)

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

    assert mock_generate.mock_calls == [call(2, 5)]
    assert mock_settings.mock_calls == [call()]
    assert mock_settings_instance.mock_calls == []
    reset_mocks()


@pytest.mark.parametrize(
    "mode,output_root_provided,expected_method,expected_output_pattern",
    [
        ("db", False, "generate_and_save2database", "Inserted 2 synthetic_case records."),
        ("file", True, "generate_and_save2file", "Wrote files to"),
    ],
)
@patch("evaluations.case_builders.synthetic_case_orchestrator.argparse.ArgumentParser")
def test_main__success(
    mock_parser_class, tmp_files, capsys, mode, output_root_provided, expected_method, expected_output_pattern
):
    tested = SyntheticCaseOrchestrator
    mock_parser = MagicMock()
    mock_parser_class.side_effect = [mock_parser]

    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

    output_root = tmp_files if output_root_provided else None
    args = Namespace(
        batches=2,
        batch_size=5,
        category="test_category",
        mode=mode,
        output_root=output_root,
    )
    mock_parser.parse_args.side_effect = [args]

    if expected_method == "generate_and_save2database":
        mock_saved_records = [MagicMock(), MagicMock()]
        with patch.object(tested, expected_method) as mock_method:
            mock_method.side_effect = [mock_saved_records]
            tested.main()

            assert mock_parser_class.mock_calls == [call()]
            assert mock_parser.mock_calls == [
                call.add_argument("--batches", type=int, required=True),
                call.add_argument("--batch-size", type=int, required=True),
                call.add_argument("--category", type=str, required=True),
                call.add_argument(
                    "--mode",
                    choices=["db", "file"],
                    required=True,
                    help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
                ),
                call.add_argument("--output-root", type=Path, help="Required when --mode is 'file'"),
                call.parse_args(),
            ]
            assert mock_method.mock_calls == [call(args.batches, args.batch_size, args.category)]

            output = capsys.readouterr().out
            assert expected_output_pattern in output

    else:
        with patch.object(tested, expected_method) as mock_method:
            mock_method.side_effect = [None]
            tested.main()

            assert mock_parser_class.mock_calls == [call()]
            assert mock_parser.mock_calls == [
                call.add_argument("--batches", type=int, required=True),
                call.add_argument("--batch-size", type=int, required=True),
                call.add_argument("--category", type=str, required=True),
                call.add_argument(
                    "--mode",
                    choices=["db", "file"],
                    required=True,
                    help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
                ),
                call.add_argument("--output-root", type=Path, help="Required when --mode is 'file'"),
                call.parse_args(),
            ]
            assert mock_method.mock_calls == [call(args.batches, args.batch_size, args.category, args.output_root)]

            output = capsys.readouterr().out
            assert expected_output_pattern in output
    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.argparse.ArgumentParser")
def test_main__validation_error(mock_parser_class):
    tested = SyntheticCaseOrchestrator
    mock_parser = MagicMock()
    mock_parser_class.side_effect = [mock_parser]

    def reset_mocks():
        mock_parser_class.reset_mock()
        mock_parser.reset_mock()

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

    assert mock_parser_class.mock_calls == [call()]
    assert mock_parser.mock_calls == [
        call.add_argument("--batches", type=int, required=True),
        call.add_argument("--batch-size", type=int, required=True),
        call.add_argument("--category", type=str, required=True),
        call.add_argument(
            "--mode",
            choices=["db", "file"],
            required=True,
            help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
        ),
        call.add_argument("--output-root", type=Path, help="Required when --mode is 'file'"),
        call.parse_args(),
        call.error("--output-root is required in file mode"),
    ]
    reset_mocks()
