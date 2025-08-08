import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from argparse import Namespace
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.structures.chart import Chart
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.structures.graded_criterion import GradedCriterion
from hyperscribe.structures.line import Line


def _invalid_path(tmp_path: Path) -> Path:
    # Helper to capture the real Path("invalid_output.json") in tmp_path
    return tmp_path / "invalid_output.json"


@pytest.mark.parametrize(
    "returned_class,test_data,expected_result",
    [
        # chart returned_class
        (
            Chart,
            {
                "demographicStr": "test demographic",
                "conditionHistory": [{"code": "Z87.891", "label": "Personal history of tobacco use", "uuid": "uuid-1"}],
                "currentAllergies": [{"code": "Z88.1", "label": "Allergy to penicillin", "uuid": "uuid-2"}],
                "currentConditions": [{"code": "J45.9", "label": "Asthma, unspecified", "uuid": "uuid-3"}],
                "currentMedications": [{"code": "329498", "label": "Albuterol inhaler", "uuid": "uuid-4"}],
                "currentGoals": [{"code": "", "label": "Control symptoms", "uuid": "uuid-5"}],
                "familyHistory": [],
                "surgeryHistory": [{"code": "0DT70ZZ", "label": "Appendectomy", "uuid": "uuid-6"}],
            },
            lambda data: Chart.load_from_json(data),
        ),
        # transcript returned_class
        (
            list[Line],
            [{"speaker": "Clinician", "text": "Hello"}, {"speaker": "Patient", "text": "Hi there"}],
            lambda data: Line.load_from_json(data),
        ),
        # profile returned_class
        (
            list[PatientProfile],
            {"Patient 1": "Profile text 1", "Patient 2": "Profile text 2"},
            lambda data: [PatientProfile(name=name, profile=profile) for name, profile in data.items()],
        ),
        # rubric returned_class
        (
            list[RubricCriterion],
            [
                {"criterion": "Reward for accuracy", "weight": 50, "sense": "positive"},
                {"criterion": "Penalize for errors", "weight": 30, "sense": "negative"},
            ],
            lambda data: [RubricCriterion(**item) for item in data],
        ),
        # grades returned_class
        (
            list[GradedCriterion],
            [
                {"id": 0, "rationale": "Good work", "satisfaction": 80},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 40},
            ],
            lambda data: [GradedCriterion(**item, score=-0.000) for item in data],
        ),
    ],
)
@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate__json_success(mock_llm_cls, mock_memory_log, tmp_path, returned_class, test_data, expected_result):
    result_obj = Namespace(has_error=False, content=[test_data], error="")

    mock_llm = MagicMock()
    mock_llm.chat.return_value = result_obj
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.side_effect = ["MemoryLogInstance"]

    schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}
    tested = HelperSyntheticJson.generate_json(
        vendor_key=VendorKey("openai", "dummy_key"),
        system_prompt=["System prompt"],
        user_prompt=["User prompt"],
        schema=schema,
        returned_class=returned_class,
    )

    expected = expected_result(test_data)

    assert tested == expected
    assert not (tmp_path / "invalid_output.json").exists()

    expected_calls = [
        call("MemoryLogInstance", "dummy_key", with_audit=False, temperature=1.0),
        call().set_system_prompt(["System prompt"]),
        call().set_user_prompt(["User prompt"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    assert mock_llm.chat.call_count == 1
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls


@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__unsupported_returned_class(mock_llm_cls, mock_memory_log):
    # Test unsupported returned_class raises ValueError
    result_obj = Namespace(has_error=False, content=[{"key": "value"}], error="")

    mock_llm = MagicMock()
    mock_llm.chat.return_value = result_obj
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.return_value = "MemoryLogInstance"

    def reset_mocks():
        mock_llm_cls.reset_mock()
        mock_memory_log.reset_mock()
        mock_llm.reset_mock()

    schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}

    with pytest.raises(ValueError, match="Unsupported returned_class"):
        HelperSyntheticJson.generate_json(
            vendor_key=VendorKey("openai", "dummy_key"),
            system_prompt=["System prompt"],
            user_prompt=["User prompt"],
            schema=schema,
            returned_class=dict,
        )

    expected_calls = [
        call("MemoryLogInstance", "dummy_key", with_audit=False, temperature=1.0),
        call().set_system_prompt(["System prompt"]),
        call().set_user_prompt(["User prompt"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__parses_fenced_json(mock_llm_cls, mock_memory_log, tmp_path):
    chart_data = {
        "demographicStr": "test demographic",
        "conditionHistory": [{"code": "Z87.891", "label": "Personal history of tobacco use", "uuid": "uuid-1"}],
        "currentAllergies": [{"code": "Z88.1", "label": "Allergy to penicillin", "uuid": "uuid-2"}],
        "currentConditions": [{"code": "J45.9", "label": "Asthma, unspecified", "uuid": "uuid-3"}],
        "currentMedications": [{"code": "329498", "label": "Albuterol inhaler", "uuid": "uuid-4"}],
        "currentGoals": [{"code": "", "label": "Control symptoms", "uuid": "uuid-5"}],
        "familyHistory": [],
        "surgeryHistory": [{"code": "0DT70ZZ", "label": "Appendectomy", "uuid": "uuid-6"}],
    }
    result_obj = Namespace(has_error=False, content=[chart_data], error="network fail")

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [result_obj]
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.side_effect = ["MemoryLogInstance"]
    schema = {"type": "object"}

    tested = HelperSyntheticJson.generate_json(
        vendor_key=VendorKey("openai", "dummy"),
        system_prompt=["system"],
        user_prompt=["user"],
        schema=schema,
        returned_class=Chart,
    )
    expected = Chart.load_from_json(chart_data)
    assert tested == expected

    expected_calls = [
        call("MemoryLogInstance", "dummy", with_audit=False, temperature=1.0),
        call().set_system_prompt(["system"]),
        call().set_user_prompt(["user"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    assert mock_llm.chat.call_count == 1
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls


@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__chat_error_exits(mock_llm_cls, mock_memory_log, tmp_path):
    # LLM.chat signals a lower-level error
    schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}
    tested_obj = Namespace(has_error=True, content="irrelevant", error="network fail")

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [tested_obj]
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.side_effect = ["MemoryLogInstance"]

    invalid = _invalid_path(tmp_path)
    with (
        patch("evaluations.case_builders.helper_synthetic_json.Path", return_value=invalid),
        patch("evaluations.case_builders.helper_synthetic_json.sys.exit", side_effect=SystemExit) as mock_exit,
    ):
        with pytest.raises(SystemExit):
            HelperSyntheticJson.generate_json(
                vendor_key=VendorKey("openai", "dummy"),
                system_prompt=["system"],
                user_prompt=["user"],
                schema=schema,
                returned_class=Chart,
            )

    # system exit invoked, so no content access but check on attributes
    assert tested_obj.has_error is True
    assert tested_obj.error == "network fail"
    assert mock_exit.mock_calls == [call(1)]

    expected_calls = [
        call("MemoryLogInstance", "dummy", with_audit=False, temperature=1.0),
        call().set_system_prompt(["system"]),
        call().set_user_prompt(["user"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    assert mock_llm.chat.call_count == 1
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls
