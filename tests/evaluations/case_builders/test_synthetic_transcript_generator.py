import json, random, argparse, pytest, hashlib
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from evaluations.case_builders.synthetic_transcript_generator import SyntheticTranscriptGenerator, HelperSyntheticJson
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.constants import Constants as SpecificationConstants

def create_fake_profiles_file(tmp_path: Path) -> Path:
    fake_profiles = tmp_path / "profiles.json"
    fake_profiles.write_text(json.dumps({"Patient 1": "AAA", "Patient 2": "BBB"}))
    return fake_profiles

def test__load_profiles(tmp_path):
    expected = {"Alice": "profile1", "Bob": "profile2"}
    profiles_file = tmp_path / "profiles.json"
    profiles_file.write_text(json.dumps(expected))

    tested = SyntheticTranscriptGenerator(VendorKey("openai", "KEY"), input_path=profiles_file, output_path=tmp_path)
    result = tested._load_profiles()
    assert result == expected

@patch("evaluations.case_builders.synthetic_transcript_generator.random.choice")
def test__random_bucket(mock_choice):
    expected_keys = list(SpecificationConstants.TURN_BUCKETS.keys())
    forced_returns = expected_keys
    mock_choice.side_effect = forced_returns

    results = [SyntheticTranscriptGenerator._random_bucket() for _ in range(3)]
    assert results == forced_returns
    assert all(result in expected_keys for result in results)

    #mock calls
    expected_calls = [call(expected_keys) for _ in range(3)]
    assert mock_choice.mock_calls == expected_calls


@patch.object(random, "uniform", return_value=1.25)
@patch.object(random, "randint", return_value=3)
@patch.object(random, "sample") 
@patch.object(random, "choice")
def test__make_specifications(mock_choice, mock_sample, mock_randint, mock_uniform, tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)

    mock_choice.side_effect = (
        ["short"]
        + ["Clinician"]
        + ["Patient"] * 2
        + [SpecificationConstants.PRESSURE_POOL[0]]
        + [SpecificationConstants.CLINICIAN_PERSONAS[0]]
        + [SpecificationConstants.PATIENT_PERSONAS[0]]
    )

    mock_sample.return_value = [SpecificationConstants.MOOD_POOL[0], SpecificationConstants.MOOD_POOL[1]]

    specifications = tested._make_specifications()
    assert specifications["bucket"] == "short"
    assert specifications["turn_total"] == 3
    assert specifications["speaker_sequence"] == ["Clinician", "Patient", "Patient"]
    assert specifications["ratio"] == 1.25
    assert specifications["mood"] == mock_sample.return_value

    assert mock_randint.mock_calls == [call(2, 4)]
    assert mock_uniform.mock_calls == [call(0.5, 2.0)]

    expected_sample_calls = [call(SpecificationConstants.MOOD_POOL, k=2)]
    assert mock_sample.mock_calls == expected_sample_calls
    
    expected_choice_calls = [
        call(list(SpecificationConstants.TURN_BUCKETS.keys())),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(SpecificationConstants.PRESSURE_POOL),
        call(SpecificationConstants.CLINICIAN_PERSONAS),
        call(SpecificationConstants.PATIENT_PERSONAS),
    ]
    assert mock_choice.mock_calls == expected_choice_calls

def test_schema_transcript(tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)
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
                    "speaker": {"type": "string",
                                "description": "Who is talking for this turn, either 'Clinician' or 'Patient'."},
                    "text":    {"type": "string",
                                "description": "Words spoken during the turn."},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        }
    assert result == expected


def test__build_prompt(tmp_path):
    tested = SyntheticTranscriptGenerator(VendorKey("openai", "MY_KEY"), create_fake_profiles_file(tmp_path), tmp_path)

    specifications = {
        "turn_total": 2,
        "speaker_sequence": ["Clinician", "Patient"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": "",
    }
    schema = {"type": "array"}

    system_prompt_no_previous, _ = tested._build_prompt("profile text", specifications, schema)
    assert "Avoid starting with any of these previous first lines:" not in "\n".join(system_prompt_no_previous)

    tested.seen_openings.add("previous first line")
    system_prompt_previous_lines, user_prompt_previous_lines = tested._build_prompt("profile text", specifications, schema)
    
    combined_sys = "\n".join(system_prompt_previous_lines)
    assert "Avoid starting with any of these previous first lines: previous first line" in combined_sys
    expected_system_md5 = "8407fd613773ae1c4494989d79fd4588"
    expected_user_md5   = "6257d98e369d9359b5900eec00953b5a"
    result_system_md5 = hashlib.md5("\n".join(system_prompt_previous_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(user_prompt_previous_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt",
    return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_specifications",
    return_value={
        "bucket": "short",
        "turn_total": 1,
        "speaker_sequence": ["Clinician"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": ""})
@patch.object(HelperSyntheticJson, "generate_json", return_value=[{"speaker": "Clinician", "text": "Sample text"}])
def test_generate_transcript_for_profile__success(mock_generate_json, mock_make_specifications, mock_build_prompt, mock_schema_transcript, tmp_path):
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(
        vendor_key=VendorKey("openai", "KEY"), input_path=profiles, output_path=tmp_path)

    profile_text = "Sample profile"
    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda _: expected_schema
    transcript, result_specifications = tested.generate_transcript_for_profile(profile_text)

    expected_transcript = [{"speaker": "Clinician", "text": "Sample text"}]
    assert transcript == expected_transcript
    assert result_specifications == mock_make_specifications.return_value
    assert "sample text" in tested.seen_openings

    assert mock_make_specifications.mock_calls == [call()]
    assert mock_schema_transcript.mock_calls == [call(1)] #turn_total count from patch.object, int passed instead of dict.
    assert mock_build_prompt.mock_calls == [call("Sample profile", mock_make_specifications.return_value, expected_schema)]

    assert mock_generate_json.mock_calls == [call(
        vendor_key=tested.vendor_key,
        schema=expected_schema,
        system_prompt=["System Prompt"],
        user_prompt=["User Prompt"]
    )]


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt",
    return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_specifications",
    return_value={
        "bucket": "short",
        "turn_total": 1,
        "speaker_sequence": ["Clinician"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": "",})
@patch.object(HelperSyntheticJson, "generate_json", side_effect=ValueError("Invalid JSON"))
def test_generate_transcript_for_profile__bad_json_raises(mock_generate_json, mock_make_specifications, mock_build_prompt, mock_schema_transcript, tmp_path):
    profiles = create_fake_profiles_file(tmp_path)
    vendor_key=VendorKey("openai", "KEY")
    tested = SyntheticTranscriptGenerator(vendor_key, input_path=profiles, output_path=tmp_path)

    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda _: expected_schema
    profile_text = "Sample profile"
    with pytest.raises(ValueError) as exc_info:
        tested.generate_transcript_for_profile(profile_text)
    assert "Invalid JSON" in str(exc_info.value)

    assert mock_make_specifications.mock_calls == [call()]
    assert mock_schema_transcript.mock_calls == [call(1)] #turn_total count from patch.object, int passed instead of dict.
    assert mock_build_prompt.mock_calls == [call("Sample profile", mock_make_specifications.return_value, expected_schema)]

    assert mock_generate_json.mock_calls == [call(
        vendor_key=tested.vendor_key,
        schema=expected_schema,
        system_prompt=["System Prompt"],
        user_prompt=["User Prompt"]
    )]

@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt",
    return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_specifications",
    return_value={
        "bucket": "short",
        "turn_total": 1,
        "speaker_sequence": ["Clinician"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": ""})
@patch.object(HelperSyntheticJson, "generate_json", return_value=[{"speaker": "Clinician", "text": "Content"}])
def test_run(mock_generate_json, mock_make_specifications, mock_build_prompt, mock_schema_transcript, tmp_path):
    input_file = create_fake_profiles_file(tmp_path)
    output_dir = tmp_path / "output"
    tested = SyntheticTranscriptGenerator(
        vendor_key=VendorKey("openai", "KEY"), input_path=input_file, output_path=output_dir)
    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda _: expected_schema

    #patient 2 start.
    tested.run(start_index=2, limit=1)
    result_directory = output_dir / "Patient_2"
    assert (result_directory / "transcript.json").exists()
    assert (result_directory / "specifications.json").exists()


    assert mock_make_specifications.mock_calls == [call()]
    assert mock_schema_transcript.mock_calls == [call(1)] #turn_total count from patch.object, int passed instead of dict.
    assert mock_build_prompt.mock_calls == [call("BBB", mock_make_specifications.return_value, expected_schema)]

    assert mock_generate_json.mock_calls == [call(
        vendor_key=tested.vendor_key,
        schema=expected_schema,
        system_prompt=["System Prompt"],
        user_prompt=["User Prompt"]
    )]
   

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
    assert mock_run.mock_calls == [call(start_index=5, limit=10)]
