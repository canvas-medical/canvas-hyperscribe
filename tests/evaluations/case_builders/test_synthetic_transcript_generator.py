import json, random, pytest, hashlib
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from evaluations.case_builders.synthetic_transcript_generator import SyntheticTranscriptGenerator, HelperSyntheticJson
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.specification import Specification
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from unittest.mock import call
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.line import Line


def create_fake_profiles_file(tmp_path: Path) -> Path:
    fake_profiles = tmp_path / "profiles.json"
    fake_profiles.write_text(json.dumps({"Patient 1": "AAA", "Patient 2": "BBB"}))
    return fake_profiles


def test__load_profiles(tmp_path):
    profiles_dict = {"Alice": "profile1", "Bob": "profile2"}
    expected = [
        PatientProfile(name="Alice", profile="profile1"),
        PatientProfile(name="Bob", profile="profile2"),
    ]
    profiles_file = tmp_path / "profiles.json"
    profiles_file.write_text(json.dumps(profiles_dict))

    result = SyntheticTranscriptGenerator.load_profiles_from_file(profiles_file)
    assert result == expected


@patch("evaluations.case_builders.synthetic_transcript_generator.random.choice")
def test__random_bucket(mock_choice):
    expected_keys = list(SyntheticCaseTurnBuckets)
    mock_choice.side_effect = expected_keys
    results = [SyntheticTranscriptGenerator._random_bucket() for _ in range(3)]
    assert results == expected_keys
    assert all(isinstance(r, SyntheticCaseTurnBuckets) for r in results)

    expected_calls = [call(expected_keys) for _ in range(3)]
    assert mock_choice.mock_calls == expected_calls


@patch.object(random, "uniform", return_value=1.25)
@patch.object(random, "randint", return_value=3)
@patch.object(random, "sample")
@patch.object(random, "choice")
def test__make_specifications(mock_choice, mock_sample, mock_randint, mock_uniform):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = [
        PatientProfile(name="Patient 1", profile="AAA"),
        PatientProfile(name="Patient 2", profile="BBB"),
    ]
    tested = SyntheticTranscriptGenerator(vendor_key, profiles)

    mock_choice.side_effect = (
        [SyntheticCaseTurnBuckets.SHORT]
        + ["Clinician"]
        + ["Patient"] * 2
        + [SyntheticCasePressure.TIME_PRESSURE]
        + [SyntheticCaseClinicianStyle.WARM_CHATTY]
        + [SyntheticCasePatientStyle.ANXIOUS_TALKATIVE]
    )

    mock_sample.side_effect = [[SyntheticCaseMood.PATIENT_FRUSTRATED, SyntheticCaseMood.PATIENT_TEARFUL]]

    specifications = tested._make_specifications()
    assert specifications.bucket == SyntheticCaseTurnBuckets.SHORT
    assert specifications.turn_total == 3
    assert specifications.speaker_sequence == ["Clinician", "Patient", "Patient"]
    assert specifications.ratio == 1.25
    # mood will be enum objects, not string values
    assert len(specifications.mood) == 2

    assert mock_randint.mock_calls == [call(2, 4)]
    assert mock_uniform.mock_calls == [call(0.5, 2.0)]

    expected_sample_calls = [call(list(SyntheticCaseMood), k=2)]
    assert mock_sample.mock_calls == expected_sample_calls

    expected_choice_calls = [
        call(list(SyntheticCaseTurnBuckets)),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(list(SyntheticCasePressure)),
        call(list(SyntheticCaseClinicianStyle)),
        call(list(SyntheticCasePatientStyle)),
    ]
    assert mock_choice.mock_calls == expected_choice_calls


def test_schema_transcript():
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = [
        PatientProfile(name="Patient 1", profile="AAA"),
        PatientProfile(name="Patient 2", profile="BBB"),
    ]
    tested = SyntheticTranscriptGenerator(vendor_key, profiles)
    turn_total = 37
    result = tested.schema_transcript(turn_total)
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 37,
        "maxItems": 37,
        "items": {
            "type": "object",
            "properties": {
                "speaker": {
                    "type": "string",
                    "description": "Who is talking for this turn, either 'Clinician' or 'Patient'.",
                },
                "text": {"type": "string", "description": "Words spoken during the turn."},
            },
            "required": ["speaker", "text"],
            "additionalProperties": False,
        },
    }
    assert result == expected


def test__build_prompt():
    tested = SyntheticTranscriptGenerator(VendorKey("openai", "MY_KEY"), {})

    specifications = Specification(
        turn_total=2,
        speaker_sequence=["Clinician", "Patient"],
        ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )
    schema = {"type": "array"}

    system_prompt_no_previous, _ = tested._build_prompt("profile text", specifications, schema)
    assert "Avoid starting with any of these previous first lines:" not in "\n".join(system_prompt_no_previous)

    tested.seen_openings.add("previous first line")
    system_prompt_previous_lines, user_prompt_previous_lines = tested._build_prompt(
        "profile text", specifications, schema
    )

    combined_sys = "\n".join(system_prompt_previous_lines)
    assert "Avoid starting with any of these previous first lines: previous first line" in combined_sys
    expected_system_md5 = "8407fd613773ae1c4494989d79fd4588"
    expected_user_md5 = "ec8ba19d457bb9a2a5ca22c2d23fae25"
    result_system_md5 = hashlib.md5("\n".join(system_prompt_previous_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(user_prompt_previous_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_specifications")
@patch.object(HelperSyntheticJson, "generate_json", return_value=[Line(speaker="Clinician", text="Sample text")])
def test_generate_transcript_for_profile__success(
    mock_generate_json, mock_make_specifications, mock_build_prompt, mock_schema_transcript
):
    profiles = [
        PatientProfile(name="Patient 1", profile="AAA"),
        PatientProfile(name="Patient 2", profile="BBB"),
    ]
    tested = SyntheticTranscriptGenerator(vendor_key=VendorKey("openai", "KEY"), profiles=profiles)

    # Create a proper Specification mock return value
    mock_spec = Specification(
        turn_total=1,
        speaker_sequence=["Clinician"],
        ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )
    mock_make_specifications.side_effect = [mock_spec]

    patient_profile = PatientProfile(name="Sample Patient", profile="Sample profile")
    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda _: expected_schema
    transcript, result_specifications = tested.generate_transcript_for_profile(patient_profile)

    # transcript should be Line objects, not dicts
    assert len(transcript) == 1
    assert transcript[0].speaker == "Clinician"
    assert transcript[0].text == "Sample text"
    assert result_specifications == mock_spec
    assert "sample text" in tested.seen_openings

    assert mock_make_specifications.mock_calls == [call()]
    assert mock_schema_transcript.mock_calls == [
        call(1)
    ]  # turn_total count from patch.object, int passed instead of dict.
    assert mock_build_prompt.mock_calls == [call("Sample profile", mock_spec, expected_schema)]

    assert mock_generate_json.mock_calls == [
        call(
            vendor_key=tested.vendor_key,
            system_prompt=["System Prompt"],
            user_prompt=["User Prompt"],
            schema=expected_schema,
            returned_class=list[Line],
        )
    ]


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_specifications")
@patch.object(HelperSyntheticJson, "generate_json", side_effect=ValueError("Invalid JSON"))
def test_generate_transcript_for_profile__bad_json_raises(
    mock_generate_json, mock_make_specifications, mock_build_prompt, mock_schema_transcript
):
    profiles = [
        PatientProfile(name="Patient 1", profile="AAA"),
        PatientProfile(name="Patient 2", profile="BBB"),
    ]
    vendor_key = VendorKey("openai", "KEY")
    tested = SyntheticTranscriptGenerator(vendor_key, profiles=profiles)

    # Create a proper Specification mock return value
    mock_spec = Specification(
        turn_total=1,
        speaker_sequence=["Clinician"],
        ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )
    mock_make_specifications.side_effect = [mock_spec]

    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda _: expected_schema
    patient_profile = PatientProfile(name="Sample Patient", profile="Sample profile")
    with pytest.raises(ValueError) as exc_info:
        tested.generate_transcript_for_profile(patient_profile)
    assert "Invalid JSON" in str(exc_info.value)

    assert mock_make_specifications.mock_calls == [call()]
    assert mock_schema_transcript.mock_calls == [
        call(1)
    ]  # turn_total count from patch.object, int passed instead of dict.
    assert mock_build_prompt.mock_calls == [call("Sample profile", mock_spec, expected_schema)]

    assert mock_generate_json.mock_calls == [
        call(
            vendor_key=tested.vendor_key,
            system_prompt=["System Prompt"],
            user_prompt=["User Prompt"],
            schema=expected_schema,
            returned_class=list[Line],
        )
    ]


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt", return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_specifications")
@patch.object(HelperSyntheticJson, "generate_json", return_value=[Line(speaker="Clinician", text="Content")])
def test_run(mock_generate_json, mock_make_specifications, mock_build_prompt, mock_schema_transcript, tmp_path):
    profiles = [
        PatientProfile(name="Patient 1", profile="AAA"),
        PatientProfile(name="Patient 2", profile="BBB"),
    ]
    tested = SyntheticTranscriptGenerator(vendor_key=VendorKey("openai", "KEY"), profiles=profiles)

    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda _: expected_schema

    # Create a proper Specification mock return value
    mock_spec = Specification(
        turn_total=1,
        speaker_sequence=["Clinician"],
        ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )
    mock_make_specifications.side_effect = [mock_spec]

    output_dir = tmp_path / "output"

    # patient 2 start.
    tested.run(start_index=2, limit=1, output_path=output_dir)
    result_directory = output_dir / "Patient_2"
    assert (result_directory / "transcript.json").exists()
    assert (result_directory / "specifications.json").exists()

    assert mock_make_specifications.mock_calls == [call()]
    assert mock_schema_transcript.mock_calls == [
        call(1)
    ]  # turn_total count from patch.object, int passed instead of dict.
    assert mock_build_prompt.mock_calls == [call("BBB", mock_spec, expected_schema)]

    assert mock_generate_json.mock_calls == [
        call(
            vendor_key=tested.vendor_key,
            system_prompt=["System Prompt"],
            user_prompt=["User Prompt"],
            schema=expected_schema,
            returned_class=list[Line],
        )
    ]


@patch("evaluations.case_builders.synthetic_transcript_generator.HelperEvaluation.settings")
@patch("evaluations.case_builders.synthetic_transcript_generator.argparse.ArgumentParser.parse_args")
@patch.object(SyntheticTranscriptGenerator, "run")
def test_main(mock_run, mock_parse_args, mock_settings, tmp_path):
    fake_input = create_fake_profiles_file(tmp_path)
    fake_output = tmp_path / "output"
    fake_args = Namespace(input=fake_input, output=fake_output, start=5, limit=10)
    mock_parse_args.return_value = fake_args

    fake_vendor_key = VendorKey("openai", "DUMMY")
    dummy_settings = MagicMock()
    dummy_settings.llm_text = fake_vendor_key
    mock_settings.return_value = dummy_settings

    SyntheticTranscriptGenerator.main()

    assert mock_parse_args.mock_calls == [call()]
    assert mock_settings.mock_calls == [call()]
    assert mock_run.mock_calls == [call(start_index=5, limit=10, output_path=fake_output)]
