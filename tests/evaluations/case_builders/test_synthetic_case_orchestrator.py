import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

import pytest

from evaluations.case_builders.synthetic_case_orchestrator import SyntheticCaseOrchestrator
from evaluations.structures.chart import Chart
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord
from evaluations.structures.specification import Specification
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.line import Line
from hyperscribe.structures.medication_cached import MedicationCached
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockClass


@pytest.fixture
def tmp_files(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    return output_root


@pytest.fixture
def sample_case_synthetic_pairs():
    case_record = CaseRecord(
        id=1,
        name="John Doe",
        transcript={"cycle_001": []},
        limited_chart=Chart(
            demographic_str="",
            condition_history=[],
            current_allergies=[],
            current_conditions=[],
            current_medications=[],
            current_goals=[],
            family_history=[],
            surgery_history=[],
        ),
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
        text_llm_vendor="theVendor",
        text_llm_name="theModel",
        temperature=1.37,
        id=1,
    )
    return [(case_record, synthetic_record)]


@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
def test___init__(mock_profile_generator_class, tmp_files):
    mock_profile_generator = MagicMock()
    mock_profile_generator_class.side_effect = [mock_profile_generator]

    def reset_mocks():
        mock_profile_generator_class.reset_mock()
        mock_profile_generator.reset_mock()

    tested = SyntheticCaseOrchestrator("test_category")

    assert tested.category == "test_category"
    assert tested.profile_generator == mock_profile_generator
    assert mock_profile_generator_class.mock_calls == [call("test_category")]
    reset_mocks()


@pytest.mark.parametrize(
    "profiles,line_objects,expected_count",
    [
        ({"Test Patient": "Profile A"}, [{"speaker": "Clinician", "text": "Hi", "start": 1.3, "end": 2.5}], 1),
        ({"A": "P1", "B": "P2"}, [{"speaker": "Clinician", "text": "Hello", "start": 2.5, "end": 3.8}], 2),
    ],
)
@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticProfileGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticTranscriptGenerator")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticChartGenerator")
def test_generate(
    mock_chart_generator_class,
    mock_transcript_generator_class,
    mock_profile_generator_class,
    mock_helper,
    profiles,
    line_objects,
    expected_count,
):
    settings = MagicMock()

    def reset_mocks():
        mock_profile_generator_class.reset_mock()
        mock_transcript_generator_class.reset_mock()
        mock_chart_generator_class.reset_mock()
        mock_helper.reset_mock()
        settings.reset_mock()
        settings.llm_text = VendorKey(vendor="theVendor", api_key="theApiKey")

    reset_mocks()

    profiles_dict = profiles if isinstance(profiles, dict) else dict([profiles])
    profiles_list = [PatientProfile(name=name, profile=profile) for name, profile in profiles_dict.items()]
    mock_profile_generator_class.return_value.generate_batch.side_effect = [profiles_list]

    chart = Chart(
        demographic_str="Demo",
        condition_history=[CodedItem(uuid="uuid-1", label="Personal history", code="Z87.891")],
        current_allergies=[],
        current_conditions=[CodedItem(uuid="uuid-2", label="Test condition", code="J45.9")],
        current_medications=[
            MedicationCached(
                uuid="uuid-3",
                label="Test medication",
                code_rx_norm="329498",
                code_fdb="4477",
                national_drug_code="code",
                potency_unit_code="unit",
            )
        ],
        current_goals=[CodedItem(uuid="uuid-4", label="Test goal", code="")],
        family_history=[],
        surgery_history=[],
    )
    mock_chart_generator_class.return_value.generate_chart_for_profile.side_effect = [chart] * len(profiles_list)
    mock_chart_generator_class.return_value.assign_valid_uuids.side_effect = [chart] * len(profiles_list)

    lines = [Line(speaker=data["speaker"], text=data["text"]) for data in line_objects]
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
    mock_transcript_generator_class.return_value.generate_transcript_for_profile.side_effect = [
        (lines, specifications)
    ] * len(profiles_list)

    cycle_key = "cycle_001"
    mock_helper.split_lines_into_cycles.side_effect = [{cycle_key: lines}] * len(profiles_list)
    mock_helper.settings_reasoning_allowed.side_effect = [settings] * len(profiles_list)
    settings.llm_text_model.side_effect = ["theModel"] * len(profiles_list)
    settings.llm_text_temperature.side_effect = [1.76] * len(profiles_list)

    tested = SyntheticCaseOrchestrator("test_category")
    result = tested.generate(batches=1, batch_size=len(profiles_list))
    expected = expected_count

    assert len(result) == expected
    for case_record, synthetic_case_record in result:
        assert isinstance(case_record, CaseRecord)
        assert isinstance(synthetic_case_record, SyntheticCaseRecord)
        assert case_record.validation_status == CaseStatus.GENERATION
        assert synthetic_case_record.category == "test_category"
        assert synthetic_case_record.text_llm_vendor == "theVendor"
        assert synthetic_case_record.text_llm_name == "theModel"
        assert synthetic_case_record.temperature == 1.76

    calls = [call("test_category"), call().generate_batch(1, len(profiles_list))]
    assert mock_profile_generator_class.mock_calls == calls
    calls = [call(profiles=profiles_list)]
    for profile in profiles_list:
        calls.append(call().generate_chart_for_profile(profile))
        calls.append(call().assign_valid_uuids(chart.to_json()))
    assert mock_chart_generator_class.mock_calls == calls
    calls = [call(profiles=profiles_list)]
    for profile in profiles_list:
        calls.append(call().generate_transcript_for_profile(profile))
    assert mock_transcript_generator_class.mock_calls == calls
    calls = [call.settings_reasoning_allowed()]
    calls.extend([call.split_lines_into_cycles(lines)] * len(profiles_list))
    assert mock_helper.mock_calls == calls

    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.HelperEvaluation")
@patch("evaluations.case_builders.synthetic_case_orchestrator.SyntheticCaseDatastore")
@patch("evaluations.case_builders.synthetic_case_orchestrator.CaseDatastore")
@patch.object(SyntheticCaseOrchestrator, "generate")
def test_generate_and_save2database(
    mock_generate,
    mock_case_datastore_class,
    mock_synthetic_datastore_class,
    mock_helper,
    sample_case_synthetic_pairs,
):
    tested = SyntheticCaseOrchestrator

    def reset_mocks():
        mock_generate.reset_mock()
        mock_case_datastore_class.reset_mock()
        mock_synthetic_datastore_class.reset_mock()
        mock_helper.reset_mock()

    mock_generate.side_effect = [sample_case_synthetic_pairs]
    mock_helper.postgres_credentials.side_effect = ["thePostgresCredentials"]

    mock_upserted_case = MockClass(id=123)
    mock_upserted_synthetic = "theUpsertedSynthetic"
    mock_case_datastore_class.return_value.upsert.side_effect = [mock_upserted_case]
    mock_synthetic_datastore_class.return_value.upsert.side_effect = [mock_upserted_synthetic]

    result = tested.generate_and_save2database(2, 5, "test_category")
    expected = [mock_upserted_synthetic]
    assert result == expected

    calls = [call(2, 5)]
    assert mock_generate.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().upsert(sample_case_synthetic_pairs[0][0]),
    ]
    assert mock_case_datastore_class.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().upsert(
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
                text_llm_vendor="theVendor",
                text_llm_name="theModel",
                temperature=1.37,
                id=1,
            )
        ),
    ]
    assert mock_synthetic_datastore_class.mock_calls == calls
    calls = [
        call.postgres_credentials(),
    ]
    assert mock_helper.mock_calls == calls

    reset_mocks()


@patch.object(SyntheticCaseOrchestrator, "generate")
def test_generate_and_save2file(
    mock_generate,
    tmp_files,
    sample_case_synthetic_pairs,
    capsys,
):
    tested = SyntheticCaseOrchestrator
    output_root = tmp_files

    mock_generate.side_effect = [sample_case_synthetic_pairs]

    def reset_mocks():
        mock_generate.reset_mock()

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
    assert synthetic_data["turnBuckets"] == synthetic_record.turn_buckets.value

    captured = capsys.readouterr()
    assert f"Wrote {case_file}" in captured.out
    assert f"Wrote {synthetic_file}" in captured.out

    assert mock_generate.mock_calls == [call(2, 5)]
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

    def reset_mocks():
        mock_parser_class.reset_mock()

    output_root = tmp_files if output_root_provided else None
    args = MockClass(
        batches=2,
        batch_size=5,
        category="test_category",
        mode=mode,
        output_root=output_root,
    )
    mock_parser_class.return_value.parse_args.side_effect = [args]

    if expected_method == "generate_and_save2database":
        mock_saved_records = [MagicMock(), MagicMock()]
        with patch.object(tested, expected_method) as mock_method:
            mock_method.side_effect = [mock_saved_records]
            tested.main()

            assert mock_parser_class.mock_calls == [
                call(),
                call().add_argument("--batches", type=int, required=True),
                call().add_argument("--batch-size", type=int, required=True),
                call().add_argument("--category", type=str, required=True),
                call().add_argument(
                    "--mode",
                    choices=["db", "file"],
                    required=True,
                    help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
                ),
                call().add_argument("--output-root", type=Path, help="Required when --mode is 'file'"),
                call().parse_args(),
            ]
            assert mock_method.mock_calls == [call(args.batches, args.batch_size, args.category)]

            output = capsys.readouterr().out
            assert expected_output_pattern in output

    else:
        with patch.object(tested, expected_method) as mock_method:
            mock_method.side_effect = [None]
            tested.main()

            assert mock_parser_class.mock_calls == [
                call(),
                call().add_argument("--batches", type=int, required=True),
                call().add_argument("--batch-size", type=int, required=True),
                call().add_argument("--category", type=str, required=True),
                call().add_argument(
                    "--mode",
                    choices=["db", "file"],
                    required=True,
                    help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
                ),
                call().add_argument("--output-root", type=Path, help="Required when --mode is 'file'"),
                call().parse_args(),
            ]
            assert mock_method.mock_calls == [call(args.batches, args.batch_size, args.category, args.output_root)]

            output = capsys.readouterr().out
            assert expected_output_pattern in output
    reset_mocks()


@patch("evaluations.case_builders.synthetic_case_orchestrator.argparse.ArgumentParser")
def test_main__validation_error(mock_parser_class):
    tested = SyntheticCaseOrchestrator

    def reset_mocks():
        mock_parser_class.reset_mock()

    validation_args = MockClass(
        batches=2,
        batch_size=5,
        category="test_category",
        mode="file",
        output_root=None,
    )
    mock_parser_class.return_value.parse_args.side_effect = [validation_args]
    mock_parser_class.return_value.error.side_effect = [SystemExit(2)]

    with pytest.raises(SystemExit):
        tested.main()

    assert mock_parser_class.mock_calls == [
        call(),
        call().add_argument("--batches", type=int, required=True),
        call().add_argument("--batch-size", type=int, required=True),
        call().add_argument("--category", type=str, required=True),
        call().add_argument(
            "--mode",
            choices=["db", "file"],
            required=True,
            help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
        ),
        call().add_argument("--output-root", type=Path, help="Required when --mode is 'file'"),
        call().parse_args(),
        call().error("--output-root is required in file mode"),
    ]
    reset_mocks()
