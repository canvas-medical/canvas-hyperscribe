from datetime import UTC
from pathlib import Path
from unittest.mock import patch, call, MagicMock, mock_open

from evaluations.datastores.postgres.case import Case as CaseDatastore
from evaluations.datastores.postgres.rubric import Rubric as RubricDatastore
from evaluations.datastores.postgres.synthetic_case import SyntheticCase as SyntheticCaseDatastore
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.line import Line
from load_synthetic_cases import SyntheticCaseLoader


def test_load_json_file():
    tested = SyntheticCaseLoader
    mock_file_path = MagicMock(spec=Path)

    # Test loading dict
    test_data = {"key": "value"}
    mock_file_path.open.return_value.__enter__.return_value = mock_open(read_data='{"key": "value"}').return_value

    with patch("json.load") as mock_json_load:
        mock_json_load.side_effect = [test_data]
        result = tested.load_json_file(mock_file_path)
        expected = test_data
        assert result == expected

        calls = [call(mock_file_path.open.return_value.__enter__.return_value)]
        assert mock_json_load.mock_calls == calls

    # Test loading list
    test_data = [{"key": "value"}]
    mock_file_path.open.return_value.__enter__.return_value = mock_open(read_data='[{"key": "value"}]').return_value

    with patch("json.load") as mock_json_load:
        mock_json_load.side_effect = [test_data]
        result = tested.load_json_file(mock_file_path)
        expected = test_data
        assert result == expected

        calls = [call(mock_file_path.open.return_value.__enter__.return_value)]
        assert mock_json_load.mock_calls == calls


@patch.object(SyntheticCaseLoader, "load_json_file")
@patch("load_synthetic_cases.Path")
@patch("load_synthetic_cases.Line")
@patch("load_synthetic_cases.json")
def test_process_patient_directory(mock_json, mock_line, mock_path, mock_load_json_file, capsys):
    mock_case_ds = MagicMock(spec=CaseDatastore)
    mock_synthetic_case_ds = MagicMock(spec=SyntheticCaseDatastore)
    mock_rubric_ds = MagicMock(spec=RubricDatastore)
    mock_created_case = MagicMock()
    mock_created_synthetic_case = MagicMock()
    mock_created_rubric = MagicMock()

    def reset_mocks():
        mock_load_json_file.reset_mock()
        mock_path.reset_mock()
        mock_line.reset_mock()
        mock_json.reset_mock()
        mock_case_ds.reset_mock()
        mock_synthetic_case_ds.reset_mock()
        mock_rubric_ds.reset_mock()
        mock_created_case.reset_mock()
        mock_created_synthetic_case.reset_mock()
        mock_created_rubric.reset_mock()

    tested = SyntheticCaseLoader

    # Test missing files
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.name = "Patient_1"
    mock_path_instance.__truediv__.return_value.exists.side_effect = [False]

    result = tested.process_patient_directory(
        "/path/to/Patient_1",
        mock_case_ds,
        mock_synthetic_case_ds,
        mock_rubric_ds,
        "batch_id",
    )
    expected = False
    assert result == expected

    assert capsys.readouterr().out == "\n".join(
        ["Processing Patient_1...", "  ERROR: Missing transcript.json in Patient_1", ""]
    )

    calls = [
        call("/path/to/Patient_1"),
        call("/path/to/Patient_1"),
        call().__truediv__("transcript.json"),
        call().__truediv__().exists(),
    ]
    assert mock_path.mock_calls == calls
    assert mock_load_json_file.mock_calls == []
    assert mock_case_ds.mock_calls == []
    assert mock_synthetic_case_ds.mock_calls == []
    assert mock_rubric_ds.mock_calls == []
    reset_mocks()

    # Test successful processing
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.name = "Patient_1"
    mock_path_instance.__truediv__.return_value.exists.side_effect = [True, True, True, True, True]

    transcript_data = [{"speaker": "Patient", "text": "Hello"}]
    limited_chart_data = {"chart": "data"}
    profile_data = {"Patient 1": "Profile description"}
    spec_data = {
        "turn_total": 10,
        "speaker_sequence": ["Patient", "Clinician"],
        "ratio": 1.5,
        "mood": ["patient is frustrated"],
        "pressure": "time pressure on the visit",
        "clinician_style": "warm and chatty",
        "patient_style": "anxious and talkative",
        "bucket": "medium",
    }
    rubric_data = [
        {"criterion": "theCriterion1", "weight": 1, "sense": "positive"},
        {"criterion": "theCriterion2", "weight": 2, "sense": "positive"},
        {"criterion": "theCriterion3", "weight": 3, "sense": "negative"},
    ]

    mock_load_json_file.side_effect = [transcript_data, limited_chart_data, profile_data, spec_data, rubric_data]
    mock_line.load_from_json.side_effect = [[Line(speaker="Patient", text="Hello")]]
    mock_json.dumps.side_effect = ["speaker_sequence_json"]
    mock_created_case.id = 123
    mock_case_ds.upsert.side_effect = [mock_created_case]
    mock_created_synthetic_case.id = 456
    mock_synthetic_case_ds.upsert.side_effect = [mock_created_synthetic_case]
    mock_created_rubric.id = 789
    mock_rubric_ds.upsert.side_effect = [mock_created_rubric]

    result = tested.process_patient_directory(
        "/path/to/Patient_1", mock_case_ds, mock_synthetic_case_ds, mock_rubric_ds, "batch_id"
    )
    expected = True
    assert result == expected

    output = capsys.readouterr().out
    assert "Processing Patient_1..." in output
    assert "Created case record with ID: 123" in output
    assert "Created synthetic case record with ID: 456" in output
    assert "Created rubric record with ID: 789" in output

    calls = [
        call("/path/to/Patient_1"),
        call("/path/to/Patient_1"),
        call().__truediv__("transcript.json"),
        call().__truediv__().exists(),
        call("/path/to/Patient_1"),
        call().__truediv__("limited_chart.json"),
        call().__truediv__().exists(),
        call("/path/to/Patient_1"),
        call().__truediv__("profile.json"),
        call().__truediv__().exists(),
        call("/path/to/Patient_1"),
        call().__truediv__("spec.json"),
        call().__truediv__().exists(),
        call("/path/to/Patient_1"),
        call().__truediv__("rubric.json"),
        call().__truediv__().exists(),
        call("/path/to/Patient_1"),
        call().__truediv__("transcript.json"),
        call("/path/to/Patient_1"),
        call().__truediv__("limited_chart.json"),
        call("/path/to/Patient_1"),
        call().__truediv__("profile.json"),
        call("/path/to/Patient_1"),
        call().__truediv__("spec.json"),
        call("/path/to/Patient_1"),
        call().__truediv__("rubric.json"),
    ]
    assert mock_path.mock_calls == calls

    calls = [
        call(mock_path_instance.__truediv__.return_value),
        call(mock_path_instance.__truediv__.return_value),
        call(mock_path_instance.__truediv__.return_value),
        call(mock_path_instance.__truediv__.return_value),
        call(mock_path_instance.__truediv__.return_value),
    ]
    assert mock_load_json_file.mock_calls == calls

    calls = [call(transcript_data)]
    assert mock_line.load_from_json.mock_calls == calls

    calls = []
    assert mock_json.dumps.mock_calls == calls

    # Verify CaseRecord was created with correct parameters
    assert mock_case_ds.upsert.call_count == 1
    case_record_arg = mock_case_ds.upsert.call_args[0][0]
    assert case_record_arg.name == "Patient_1"
    assert case_record_arg.profile == "Profile description"
    assert case_record_arg.batch_identifier == "batch_id"

    # Verify SyntheticCaseRecord was created with correct parameters
    assert mock_synthetic_case_ds.upsert.call_count == 1
    synthetic_case_arg = mock_synthetic_case_ds.upsert.call_args[0][0]
    assert synthetic_case_arg.case_id == 123
    assert synthetic_case_arg.category == "test"
    assert synthetic_case_arg.turn_total == 10
    assert synthetic_case_arg.text_llm_vendor == "OpenAI"
    assert synthetic_case_arg.text_llm_name == "o3"

    # Verify RubricRecord was created with correct parameters
    assert mock_rubric_ds.upsert.call_count == 1
    rubric_arg = mock_rubric_ds.upsert.call_args[0][0]
    assert rubric_arg.case_id == 123
    assert rubric_arg.author == "llm"
    assert rubric_arg.rubric == rubric_data
    assert rubric_arg.case_provenance_classification == ""
    assert rubric_arg.comments == ""
    assert rubric_arg.text_llm_vendor == "OpenAI"
    assert rubric_arg.text_llm_name == "o3"
    assert rubric_arg.temperature == 1.0

    reset_mocks()

    # Test processing error
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.name = "Patient_1"
    mock_path_instance.__truediv__.return_value.exists.side_effect = [True, True, True, True, True]
    mock_load_json_file.side_effect = [Exception("JSON error")]

    result = tested.process_patient_directory(
        "/path/to/Patient_1", mock_case_ds, mock_synthetic_case_ds, mock_rubric_ds, "batch_id"
    )
    expected = False
    assert result == expected

    output = capsys.readouterr().out
    assert "Processing Patient_1..." in output
    assert "ERROR processing Patient_1: JSON error" in output

    reset_mocks()


@patch("load_synthetic_cases.datetime")
@patch("load_synthetic_cases.glob")
@patch("load_synthetic_cases.Path")
@patch.object(HelperEvaluation, "postgres_credentials")
@patch.object(SyntheticCaseLoader, "process_patient_directory")
def test_run(mock_process_patient_directory, mock_postgres_credentials, mock_path, mock_glob, mock_datetime, capsys):
    mock_credentials = MagicMock()
    mock_case_ds = MagicMock(spec=CaseDatastore)
    mock_synthetic_case_ds = MagicMock(spec=SyntheticCaseDatastore)
    mock_rubric_ds = MagicMock(spec=RubricDatastore)

    def reset_mocks():
        mock_process_patient_directory.reset_mock()
        mock_postgres_credentials.reset_mock()
        mock_path.reset_mock()
        mock_glob.reset_mock()
        mock_datetime.reset_mock()
        mock_credentials.reset_mock()
        mock_case_ds.reset_mock()
        mock_synthetic_case_ds.reset_mock()
        mock_rubric_ds.reset_mock()

    tested = SyntheticCaseLoader

    # Test credentials not ready
    mock_postgres_credentials.side_effect = [mock_credentials]
    mock_credentials.is_ready.side_effect = [False]

    with patch.object(tested, "__init__", return_value=None):
        tested.run()

    output = capsys.readouterr().out
    assert "ERROR: Database credentials not properly configured." in output

    calls = [call()]
    assert mock_postgres_credentials.mock_calls == calls
    calls = [call()]
    assert mock_credentials.is_ready.mock_calls == calls
    assert mock_glob.mock_calls == []
    assert mock_process_patient_directory.mock_calls == []
    reset_mocks()

    # Test no directories found
    mock_postgres_credentials.side_effect = [mock_credentials]
    mock_credentials.is_ready.side_effect = [True]
    mock_glob.glob.side_effect = [[]]

    with patch("load_synthetic_cases.CaseDatastore") as mock_case_ds_class:
        with patch("load_synthetic_cases.SyntheticCaseDatastore") as mock_synthetic_case_ds_class:
            with patch("load_synthetic_cases.RubricDatastore") as mock_rubric_ds_class:
                mock_case_ds_class.return_value = mock_case_ds
                mock_synthetic_case_ds_class.return_value = mock_synthetic_case_ds
                mock_rubric_ds_class.return_value = mock_rubric_ds
                mock_datetime_instance = MagicMock()
                mock_datetime_instance.strftime.return_value = "2023-12-01T10:30"
                mock_datetime.now.return_value = mock_datetime_instance
                mock_datetime.UTC = UTC

                tested.run()

    output = capsys.readouterr().out
    assert "No Patient directories found matching pattern:" in output

    calls = [call()]
    assert mock_postgres_credentials.mock_calls == calls
    calls = [call()]
    assert mock_credentials.is_ready.mock_calls == calls
    calls = [call("evaluations/cases/synthetic_unit_cases/med_management/Patient_*")]
    assert mock_glob.glob.mock_calls == calls
    assert mock_process_patient_directory.mock_calls == []
    reset_mocks()

    # Test successful processing
    mock_postgres_credentials.side_effect = [mock_credentials]
    mock_credentials.is_ready.side_effect = [True]
    mock_glob.glob.side_effect = [["Patient_1", "Patient_2", "Patient_3"]]
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.is_dir.side_effect = [True, True, False]  # Third one is not a directory
    mock_process_patient_directory.side_effect = [True, False]  # First succeeds, second fails

    with patch("load_synthetic_cases.CaseDatastore") as mock_case_ds_class:
        with patch("load_synthetic_cases.SyntheticCaseDatastore") as mock_synthetic_case_ds_class:
            with patch("load_synthetic_cases.RubricDatastore") as mock_rubric_ds_class:
                mock_case_ds_class.return_value = mock_case_ds
                mock_synthetic_case_ds_class.return_value = mock_synthetic_case_ds
                mock_rubric_ds_class.return_value = mock_rubric_ds
                mock_datetime_instance = MagicMock()
                mock_datetime_instance.strftime.return_value = "2023-12-01T10:30"
                mock_datetime.now.return_value = mock_datetime_instance
                mock_datetime.UTC = UTC

                tested.run()

    output = capsys.readouterr().out
    assert "Found 3 Patient directories to process" in output
    assert "Using batch identifier: 2023-12-01T10:30" in output
    assert "Successfully processed 1/3 directories" in output

    calls = [call()]
    assert mock_postgres_credentials.mock_calls == calls
    calls = [call()]
    assert mock_credentials.is_ready.mock_calls == calls
    calls = [call("evaluations/cases/synthetic_unit_cases/med_management/Patient_*")]
    assert mock_glob.glob.mock_calls == calls
    calls = [call("Patient_1"), call().is_dir(), call("Patient_2"), call().is_dir(), call("Patient_3"), call().is_dir()]
    assert mock_path.mock_calls == calls
    calls = [
        call("Patient_1", mock_case_ds, mock_synthetic_case_ds, mock_rubric_ds, "2023-12-01T10:30"),
        call("Patient_2", mock_case_ds, mock_synthetic_case_ds, mock_rubric_ds, "2023-12-01T10:30"),
    ]
    assert mock_process_patient_directory.mock_calls == calls
    reset_mocks()
