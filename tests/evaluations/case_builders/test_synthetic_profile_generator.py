import json, re, pytest, hashlib
from unittest.mock import patch, call, MagicMock
from argparse import ArgumentParser, Namespace
from evaluations.case_builders.synthetic_profile_generator import SyntheticProfileGenerator
from evaluations.structures.patient_profile import PatientProfile
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.vendor_key import VendorKey


@pytest.fixture
def dummy_profiles():
    return {
        "Patient 1": "Alice takes lisinopril. Simple renewal.",
        "Patient 2": "Bob switched from metformin to insulin. Complex.",
    }


@pytest.fixture
def fake_llm_response():
    def _fake(n_pairs):
        data = {f"Patient {i + 1}": f"Mock narrative {i + 1}." for i in range(n_pairs)}
        return data

    return _fake


@pytest.fixture
def vendor_key():
    return VendorKey(vendor="openai", api_key="MY_KEY")


def test___init__(vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key)
    assert tested.vendor_key == vendor_key
    assert tested.seen_scenarios == []


def test__extract_initial_fragment(vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key)
    narrative = "First sentence. Second sentence."
    expected = "First sentence"
    result = tested._extract_initial_fragment(narrative)
    assert result == expected


def test_load_json(tmp_path):
    expected_dict = {"Alice": "Profile for Alice", "Bob": "Profile for Bob"}
    expected = [
        PatientProfile(name="Alice", profile="Profile for Alice"),
        PatientProfile(name="Bob", profile="Profile for Bob"),
    ]
    data_file = tmp_path / "profiles.json"
    data_file.write_text(json.dumps(expected_dict))

    result = SyntheticProfileGenerator.load_json(data_file)
    assert result == expected


@pytest.mark.parametrize(
    "has_error,content,error_message,should_raise,expected_system_md5,expected_user_md5,expected_chat_calls",
    [
        (
            False,
            ["diabetes-metformin"],
            None,
            False,
            "3f980752be484fa5e211623508246a12",
            "293d332b0ba5d8cdedbdfd0374468ac5",
            2,
        ),
        (True, None, "LLM API error", True, "3f980752be484fa5e211623508246a12", "293d332b0ba5d8cdedbdfd0374468ac5", 1),
    ],
)
@patch("evaluations.case_builders.synthetic_profile_generator.MemoryLog")
@patch("evaluations.case_builders.synthetic_profile_generator.LlmOpenai")
def test_update_patient_names(
    mock_llm_class,
    mock_memory_log,
    vendor_key: VendorKey,
    has_error,
    content,
    error_message,
    should_raise,
    expected_system_md5,
    expected_user_md5,
    expected_chat_calls,
):
    tested = SyntheticProfileGenerator(vendor_key)

    profiles = [
        PatientProfile(name="Patient 1", profile="Alice has diabetes and takes metformin"),
        PatientProfile(name="Patient 2", profile="Bob has hypertension and takes lisinopril"),
    ]

    mock_memory_instance = MagicMock()
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()

    mock_memory_log.dev_null_instance.side_effect = [mock_memory_instance] * len(profiles)
    mock_response.has_error = has_error
    mock_response.content = content
    mock_response.error = error_message
    mock_llm_instance.chat.side_effect = [mock_response] * len(profiles)
    mock_llm_class.side_effect = [mock_llm_instance] * len(profiles)

    def reset_mocks():
        mock_llm_class.reset_mock()
        mock_memory_log.reset_mock()
        mock_memory_instance.reset_mock()
        mock_llm_instance.reset_mock()
        mock_response.reset_mock()

    if should_raise:
        with pytest.raises(Exception) as exc_info:
            tested.update_patient_names(profiles)
        assert error_message in str(exc_info.value)
    else:
        result = tested.update_patient_names(profiles)
        assert len(result) == len(profiles)
        for profile in result:
            assert "-" in profile.name
            assert len(profile.name.split("-")[-1]) == 8

    # common md5 verification.
    system_prompt_calls = [call[0][0] for call in mock_llm_instance.set_system_prompt.call_args_list]
    user_prompt_calls = [call[0][0] for call in mock_llm_instance.set_user_prompt.call_args_list]

    if system_prompt_calls and user_prompt_calls:
        result_system_md5 = hashlib.md5("\n".join(system_prompt_calls[0]).encode()).hexdigest()
        result_user_md5 = hashlib.md5("\n".join(user_prompt_calls[0]).encode()).hexdigest()

        assert result_system_md5 == expected_system_md5
        assert result_user_md5 == expected_user_md5

    assert mock_llm_instance.chat.mock_calls == [call([{"type": "string"}])] * expected_chat_calls
    assert mock_memory_log.mock_calls == [call.dev_null_instance()] * expected_chat_calls
    assert (
        mock_llm_class.mock_calls
        == [call(mock_memory_instance, vendor_key.api_key, "gpt-4o", with_audit=False)] * expected_chat_calls
    )
    assert mock_response.mock_calls == []
    assert mock_memory_instance.mock_calls == []

    reset_mocks()


def test__save_combined(tmp_path, vendor_key: VendorKey):
    output_path = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key)

    profiles = [
        PatientProfile(name="Alice", profile="Profile for Alice"),
        PatientProfile(name="Bob", profile="Profile for Bob"),
    ]

    tested._save_combined(profiles, output_path)

    result = json.loads(output_path.read_text())
    expected = {"Alice": "Profile for Alice", "Bob": "Profile for Bob"}
    assert result == expected


def test__save_individuals(tmp_path, vendor_key: VendorKey):
    out_file = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key)

    profiles = [
        PatientProfile(name="Patient 1", profile="Alice takes lisinopril. Simple renewal."),
        PatientProfile(name="Patient 2", profile="Bob switched from metformin to insulin. Complex."),
    ]

    tested._save_individuals(profiles, out_file)

    for profile in profiles:
        dir_name = re.sub(r"\s+", "_", profile.name.strip())
        profile_path = tmp_path / dir_name / "profile.json"
        assert profile_path.exists()
        result = json.loads(profile_path.read_text())
        expected = {profile.name: profile.profile}
        assert result == expected


def test_schema_batch(vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key)
    count_patients = 4
    result = tested.schema_batch(count_patients)
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "minProperties": count_patients,
        "maxProperties": count_patients,
        "patternProperties": {r"^Patient\s\d+$": {"type": "string", "description": "patient profile"}},
        "additionalProperties": False,
    }
    assert result == expected


@patch.object(SyntheticProfileGenerator, "update_patient_names")
@patch.object(SyntheticProfileGenerator, "schema_batch")
@patch("evaluations.case_builders.synthetic_profile_generator.HelperSyntheticJson.generate_json")
def test_generate_batch(
    mock_generate_json, mock_schema_batch, mock_update_names, fake_llm_response, vendor_key: VendorKey
):
    def reset_mocks():
        mock_generate_json.reset_mock()
        mock_schema_batch.reset_mock()
        mock_update_names.reset_mock()

    tested = SyntheticProfileGenerator(vendor_key)
    batch_num = 2
    count = 3
    expected_batch_dict = fake_llm_response(count)
    expected_batch_data = [PatientProfile(name=name, profile=profile) for name, profile in expected_batch_dict.items()]
    expected_schema = {"expected": "schema"}
    updated_profiles = [
        PatientProfile(name=f"patient-{i + 4}-hash{i}", profile=f"Mock narrative {i + 1}.") for i in range(count)
    ]

    mock_generate_json.side_effect = [expected_batch_data]
    mock_schema_batch.side_effect = [expected_schema]
    mock_update_names.side_effect = [updated_profiles]

    result = tested.generate_batch(batch_num, count)

    expected_schema_calls = [call(count)]
    assert mock_schema_batch.mock_calls == expected_schema_calls

    # Check generate_json call with MD5 verification
    assert len(mock_generate_json.mock_calls) == 1
    _, kwargs = mock_generate_json.call_args

    # Verify prompt content using MD5 hashes
    expected_system_md5 = "d4d9c1999dcff7d0cff01745aa3da589"
    expected_user_md5 = "b3435eae8d1a3700c841178446de8c83"
    result_system_md5 = hashlib.md5("\n".join(kwargs["system_prompt"]).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(kwargs["user_prompt"]).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
    assert kwargs["vendor_key"] == vendor_key
    assert kwargs["schema"] == expected_schema

    assert mock_update_names.mock_calls == [call(expected_batch_data)]

    assert result == updated_profiles
    assert len(tested.seen_scenarios) == count

    reset_mocks()


@patch.object(SyntheticProfileGenerator, "_save_individuals")
@patch.object(SyntheticProfileGenerator, "_save_combined")
@patch.object(SyntheticProfileGenerator, "generate_batch")
def test_run(mock_generate_batch, mock_save_combined, mock_save_individuals, tmp_path, vendor_key: VendorKey):
    def reset_mocks():
        mock_generate_batch.reset_mock()
        mock_save_combined.reset_mock()
        mock_save_individuals.reset_mock()

    output_path = tmp_path / "out.json"
    tested = SyntheticProfileGenerator(vendor_key)

    tests = [
        # (batches, batch_size, expected_generate_calls)
        (1, 5, [call(1, 5)]),
        (2, 3, [call(1, 3), call(2, 3)]),
        (3, 2, [call(1, 2), call(2, 2), call(3, 2)]),
    ]

    for batches, batch_size, expected_generate_calls in tests:
        # Mock generate_batch to return some profiles
        mock_profiles = [PatientProfile(name=f"patient-{i}", profile=f"profile-{i}") for i in range(batch_size)]
        mock_generate_batch.side_effect = [mock_profiles] * batches

        tested.run(batches=batches, batch_size=batch_size, output_path=output_path)

        # Check generate_batch calls
        assert mock_generate_batch.mock_calls == expected_generate_calls

        # Check save calls - should be called once with all profiles combined
        all_profiles = mock_profiles * batches
        expected_save_combined_calls = [call(all_profiles, output_path)]
        assert mock_save_combined.mock_calls == expected_save_combined_calls

        expected_save_individuals_calls = [call(all_profiles, output_path)]
        assert mock_save_individuals.mock_calls == expected_save_individuals_calls

        reset_mocks()


@patch("pathlib.Path.mkdir")
@patch.object(ArgumentParser, "parse_args")
@patch.object(HelperEvaluation, "settings")
@patch.object(SyntheticProfileGenerator, "run")
def test_main(mock_run, mock_settings, mock_parse_args, mock_mkdir, tmp_path):
    def reset_mocks():
        mock_run.reset_mock()
        mock_settings.reset_mock()
        mock_parse_args.reset_mock()
        mock_mkdir.reset_mock()

    # Mock settings
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "MAIN_KEY")
    mock_settings.return_value = dummy_settings

    # Mock arguments
    output_path = tmp_path / "out.json"
    args = Namespace(batches=2, batch_size=5, output=output_path)
    mock_parse_args.return_value = args

    SyntheticProfileGenerator.main()

    # check mocks.
    assert mock_mkdir.mock_calls == [call(parents=True, exist_ok=True)]
    assert mock_settings.mock_calls == [call()]
    assert mock_parse_args.mock_calls == [call()]
    assert mock_run.mock_calls == [call(batches=2, batch_size=5, output_path=output_path)]

    reset_mocks()
