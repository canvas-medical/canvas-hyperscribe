import json, random, argparse, pytest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from evaluations.case_builders.synthetic_transcript_generator import SyntheticTranscriptGenerator, HelperSyntheticJson
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.constants import Constants as SpecConstants

def create_fake_profiles_file(tmp_path: Path) -> Path:
    fake_profiles = tmp_path / "profiles.json"
    fake_profiles.write_text(json.dumps({"Patient 1": "AAA", "Patient 2": "BBB"}))
    return fake_profiles

def _expected_system_prompt(seen_openings=None):
    lines = [
        "You are simulating a real outpatient medication-management discussion.",
        "Return your answer as JSON inside a fenced ```json ... ``` block.",
        "Start mid-conversation, no greetings. End mid-topic, no farewells.",
        "Follow the speaker sequence *exactly* and aim for the target C:P word ratio ±10%.",
        "Use plain language with occasional natural hesitations (e.g., “uh”, “I mean”).",
    ]
    if seen_openings:
        lines.append(
            f"Avoid starting with any of these previous first lines: {', '.join(sorted(seen_openings))}"
        )
    return lines


def _expected_user_prompt(profile_text, spec, schema):
    return [
        f"Patient profile: {profile_text}",
        "--- TRANSCRIPT SPEC ---",
        json.dumps(
            {
                "turn_total": spec["turn_total"],
                "speaker_sequence": spec["speaker_sequence"],
                "target_C_to_P_word_ratio": spec["ratio"],
            }
        ),
        "",
        f"Moods: {', '.join(spec['mood'])}",
        f"External pressure: {spec['pressure']}",
        f"Clinician persona: {spec['clinician_style']}",
        f"Patient persona: {spec['patient_style']}",
        "",
        "Instructions:",
        "1. Follow the speaker sequence exactly (same order and length).",
        "2. Hit the requested word ratio ±10%.",
        "3. Embed the mood, pressure, and personas naturally.",
        "4. Focus on medication details—dose changes, side‑effects, adherence, etc.",
        "5. No concluding pleasantries.",
        "",
        "Your JSON **must** conform to the following JSON Schema:",
        "```json",
        json.dumps(schema, indent=2),
        "```",
        "",
        "Wrap the JSON array in a fenced ```json block and output nothing else.",
    ]


def test__load_profiles(tmp_path):
    data = {"Alice": "profile1", "Bob": "profile2"}
    profiles_file = tmp_path / "profiles.json"
    profiles_file.write_text(json.dumps(data))

    dummy = Namespace(input_path=profiles_file)
    result = SyntheticTranscriptGenerator._load_profiles(dummy)
    assert result == data

def test__random_bucket():
    valid_keys = set(SpecConstants.TURN_BUCKETS.keys())
    tested = {SyntheticTranscriptGenerator._random_bucket() for _ in range(50)}
    assert tested.issubset(valid_keys)
    assert tested


@patch.object(random, "uniform", return_value=1.25)
@patch.object(random, "randint", return_value=3)
@patch.object(random, "sample") 
@patch.object(random, "choice")
def test__make_spec(mock_choice, mock_sample, _randint, _uniform, tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)

    mock_choice.side_effect = (
        ["short"]
        + ["Clinician"]
        + ["Patient"] * 2
        + [SpecConstants.PRESSURE_POOL[0]]
        + [SpecConstants.CLINICIAN_PERSONAS[0]]
        + [SpecConstants.PATIENT_PERSONAS[0]]
    )

    mock_sample.return_value = [SpecConstants.MOOD_POOL[0], SpecConstants.MOOD_POOL[1]]

    spec = tested._make_spec()
    assert spec["bucket"] == "short"
    assert spec["turn_total"] == 3
    assert spec["speaker_sequence"] == ["Clinician", "Patient", "Patient"]
    assert spec["ratio"] == 1.25
    assert spec["mood"] == mock_sample.return_value

    expected_sample_calls = [call(SpecConstants.MOOD_POOL, k=2)]
    assert mock_sample.mock_calls == expected_sample_calls

    
    expected_calls = [
        call(list(SpecConstants.TURN_BUCKETS.keys())),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(SpecConstants.PRESSURE_POOL),
        call(SpecConstants.CLINICIAN_PERSONAS),
        call(SpecConstants.PATIENT_PERSONAS),
    ]
    assert mock_choice.mock_calls == expected_calls

def test_schema_transcript(tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)
    spec = tested._make_spec()
    result = tested.schema_transcript(spec)
    expected = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": spec["turn_total"],
            "maxItems": spec["turn_total"],
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
    tested.seen_openings.add("previous first line")

    spec = {
        "turn_total": 2,
        "speaker_sequence": ["Clinician", "Patient"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": "",
    }
    
    dummy_schema = {"type": "array"}
    system_lines, user_lines = tested._build_prompt("profile text", spec, dummy_schema)

    assert system_lines == _expected_system_prompt({"previous first line"})
    assert user_lines == _expected_user_prompt("profile text", spec, dummy_schema)

    combined_system = "\n".join(system_lines)
    assert ("Avoid starting with any of these previous first lines: previous first line" in combined_system)


@patch.object(SyntheticTranscriptGenerator, "_make_spec",
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
def test_generate_transcript_for_profile__success(mock_generate_json, mock_make_spec, tmp_path):
    profiles = create_fake_profiles_file(tmp_path)
    output_dir = tmp_path / "output"
    tested = SyntheticTranscriptGenerator(
        vendor_key=VendorKey("openai", "KEY"), input_path=profiles, output_path=output_dir)

    profile_text = "Sample profile"
    transcript, spec = tested.generate_transcript_for_profile(profile_text)
    expected_transcript = [{"speaker": "Clinician", "text": "Sample text"}]

    # Build the expected schema & prompts exactly as the generator would
    expected_schema = tested.schema_transcript(spec)
    expected_system_prompt = _expected_system_prompt()  # seen_openings empty on first call
    expected_user_prompt = _expected_user_prompt(profile_text, spec, expected_schema)

    kwargs = mock_generate_json.call_args.kwargs
    assert kwargs["vendor_key"] == tested.vendor_key
    assert kwargs["schema"] == expected_schema
    assert kwargs["system_prompt"] == expected_system_prompt
    assert kwargs["user_prompt"] == expected_user_prompt

    expected_call = call(
        vendor_key=tested.vendor_key,
        system_prompt=expected_system_prompt,
        user_prompt=expected_user_prompt,
        schema=expected_schema,
    )
    assert mock_generate_json.mock_calls == [expected_call]
    assert transcript == expected_transcript
    assert "sample text" in tested.seen_openings


@patch.object(SyntheticTranscriptGenerator, "_make_spec",
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
def test_generate_transcript_for_profile__bad_json_raises(mock_generate_json, mock_make_spec, tmp_path):
    profiles = create_fake_profiles_file(tmp_path)
    vendor_key=VendorKey("openai", "KEY")
    tested = SyntheticTranscriptGenerator(vendor_key, input_path=profiles, output_path=tmp_path)

    profile_text = "Sample profile"
    with pytest.raises(ValueError) as exc_info:
        tested.generate_transcript_for_profile(profile_text)
    assert "Invalid JSON" in str(exc_info.value)

    # reconstruct the spec and schema used (from our patched return value)
    spec = mock_make_spec.return_value
    expected_schema = tested.schema_transcript(spec)
    expected_system_prompt = _expected_system_prompt()
    expected_user_prompt = _expected_user_prompt(profile_text, spec, expected_schema)

    expected_call = call(
        vendor_key=tested.vendor_key,
        system_prompt=expected_system_prompt,
        user_prompt=expected_user_prompt,
        schema=expected_schema,
    )
    assert mock_generate_json.mock_calls == [expected_call]

@patch.object(SyntheticTranscriptGenerator, "_make_spec",
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
def test_run(mock_generate_json, mock_make_spec, tmp_path):
    input_file = create_fake_profiles_file(tmp_path)
    output_dir = tmp_path / "output"
    tested = SyntheticTranscriptGenerator(
        vendor_key=VendorKey("openai", "KEY"), input_path=input_file, output_path=output_dir)

    #patient 2
    tested.run(start_index=2, limit=1)
    result_directory = output_dir / "Patient_2"
    assert (result_directory / "transcript.json").exists()
    assert (result_directory / "spec.json").exists()
    spec = mock_make_spec.return_value
    expected_schema = tested.schema_transcript(spec)
    expected_system_prompt = _expected_system_prompt()
    expected_user_prompt = _expected_user_prompt("BBB", spec, expected_schema)

    expected_call = call(
        vendor_key=tested.vendor_key,
        system_prompt=expected_system_prompt,
        user_prompt=expected_user_prompt,
        schema=expected_schema,
    )
    assert mock_generate_json.mock_calls == [expected_call]

@patch("evaluations.case_builders.synthetic_transcript_generator.SyntheticTranscriptGenerator")
@patch("evaluations.case_builders.synthetic_transcript_generator.HelperEvaluation.settings")
@patch("evaluations.case_builders.synthetic_transcript_generator.argparse.ArgumentParser.parse_args")
def test_main(mock_parse_args, mock_settings, mock_generator_class):
    fake_input = Path("input.json")
    fake_output = Path("/output")
    fake_args = argparse.Namespace(input=fake_input, output=fake_output, start=5, limit=10)
    mock_parse_args.return_value = fake_args

    fake_vendor_key = VendorKey("openai", "DUMMY")
    dummy_settings = MagicMock()
    dummy_settings.llm_text = fake_vendor_key
    mock_settings.return_value = dummy_settings

    mock_instance = MagicMock()
    mock_generator_class.return_value = mock_instance

    SyntheticTranscriptGenerator.main()

    assert mock_generator_class.call_args == call(vendor_key=fake_vendor_key,
        input_path=fake_input, output_path=fake_output)
    assert mock_instance.run.call_args == call(start_index=5, limit=10)
