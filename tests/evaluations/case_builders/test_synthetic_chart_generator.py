import json, uuid, hashlib
from pathlib import Path
from argparse import ArgumentParser
from tests.helper import MockClass
from unittest.mock import patch, MagicMock, call
from typing import Any
from evaluations.case_builders.synthetic_chart_generator import SyntheticChartGenerator
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.chart import Chart
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.constants import Constants


def test___init__():
    expected_vendor_key = VendorKey(vendor="openai", api_key="API_KEY_123")
    expected_profiles = [PatientProfile(name="Patient A", profile="Profile text")]

    tested = SyntheticChartGenerator(expected_vendor_key, expected_profiles)
    assert tested.vendor_key == expected_vendor_key
    assert tested.profiles == expected_profiles


def test_load_json(tmp_path):
    expected_dict = {"a": "aaa", "b": "bbb"}
    expected = [
        PatientProfile(name="a", profile="aaa"),
        PatientProfile(name="b", profile="bbb"),
    ]
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps(expected_dict))

    result = SyntheticChartGenerator.load_json(data_file)
    assert result == expected


def test_schema_chart():
    example_chart_known = {key: "" for key in Constants.EXAMPLE_CHART_DESCRIPTIONS}
    tested_known = SyntheticChartGenerator(VendorKey("vendor", "key"), [])

    result_schema = tested_known.schema_chart()
    assert result_schema["description"] == "Canvas-compatible chart structure with structured ChartItems"
    assert result_schema["type"] == "object"
    assert result_schema["additionalProperties"] is False
    assert set(result_schema["required"]) == set(example_chart_known.keys())

    properties = result_schema["properties"]
    assert set(properties.keys()) == set(example_chart_known.keys())

    # demographicStr should be string
    assert properties["demographicStr"]["type"] == "string"
    assert properties["demographicStr"]["description"] == "String describing patient demographics"

    # Chart item fields should have ChartItem schema
    chart_item_fields = [
        "conditionHistory",
        "currentAllergies",
        "currentConditions",
        "currentGoals",
        "familyHistory",
        "surgeryHistory",
    ]
    for field_name in chart_item_fields:
        assert properties[field_name]["type"] == "array"
        assert "items" in properties[field_name]
        # Check that items have the ChartItem schema structure
        items_schema = properties[field_name]["items"]
        assert items_schema["type"] == "object"
        assert set(items_schema["properties"].keys()) == {"code", "label", "uuid"}
        assert items_schema["required"] == ["code", "label", "uuid"]

    # currentMedications should have MedicationCached schema
    medications_schema = properties["currentMedications"]["items"]
    assert medications_schema["type"] == "object"
    assert set(medications_schema["properties"].keys()) == {
        "uuid",
        "label",
        "codeRxNorm",
        "codeFdb",
        "nationalDrugCode",
        "potencyUnitCode",
    }
    assert medications_schema["required"] == [
        "uuid",
        "label",
        "codeRxNorm",
        "codeFdb",
        "nationalDrugCode",
        "potencyUnitCode",
    ]


@patch.object(SyntheticChartGenerator, "schema_chart")
@patch("evaluations.case_builders.synthetic_chart_generator.HelperSyntheticJson.generate_json")
def test_generate_chart_for_profile(mock_generate_json, mock_schema_chart, tmp_path):
    tested_key = VendorKey(vendor="openai", api_key="LLMKEY")
    dummy_profiles = [PatientProfile(name="P1*", profile="text1"), PatientProfile(name="P2!", profile="text2")]
    tested = SyntheticChartGenerator(tested_key, dummy_profiles)

    profile_obj = PatientProfile(name="test", profile="irrelevant profile")
    expected_chart_data = {
        "demographicStr": "test demographic",
        "conditionHistory": [{"code": "Z87.891", "label": "Personal history of tobacco use", "uuid": ""}],
        "currentAllergies": [{"code": "Z88.1", "label": "Allergy to penicillin", "uuid": ""}],
        "currentConditions": [{"code": "J45.9", "label": "Asthma, unspecified", "uuid": ""}],
        "currentMedications": [
            {
                "uuid": "",
                "label": "Albuterol inhaler",
                "codeRxNorm": "329498",
                "codeFdb": "",
                "nationalDrugCode": "",
                "potencyUnitCode": "",
            }
        ],
        "currentGoals": [{"code": "", "label": "Control asthma symptoms", "uuid": ""}],
        "familyHistory": [],
        "surgeryHistory": [{"code": "0DT70ZZ", "label": "Appendectomy", "uuid": ""}],
    }
    expected_chart = Chart.load_from_json(expected_chart_data)
    mock_generate_json.side_effect = [expected_chart]
    expected_schema = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}
    mock_schema_chart.side_effect = lambda: expected_schema

    result = tested.generate_chart_for_profile(profile_obj)
    assert result == expected_chart
    assert mock_schema_chart.mock_calls == [call()]

    assert len(mock_generate_json.mock_calls) == 1
    _, kwargs = mock_generate_json.call_args
    expected_system_md5 = "2dd6a8f62a929edbf394a2eb17705b97"
    expected_user_md5 = "47247de2ca279bcdda4a878451dee2ee"
    result_system_md5 = hashlib.md5("\n".join(kwargs["system_prompt"]).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(kwargs["user_prompt"]).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
    assert kwargs["vendor_key"] == tested.vendor_key
    assert kwargs["schema"] == expected_schema


def test_assign_valid_uuids():
    tested = SyntheticChartGenerator(VendorKey("v", "k"), [])
    input_chart = {"uuid": "old", "nested": [{"uuid": "old2"}, {"not_uuid": 123}]}
    result = tested.assign_valid_uuids(input_chart)

    assert result["uuid"] != "old"
    uuid.UUID(result["uuid"])
    nested_uuid = result["nested"][0]["uuid"]
    assert nested_uuid != "old2"
    uuid.UUID(nested_uuid)
    assert result["nested"][1]["not_uuid"] == 123


@patch.object(SyntheticChartGenerator, "assign_valid_uuids")
@patch.object(SyntheticChartGenerator, "generate_chart_for_profile")
def test_run_range(mock_generate, mock_assign, tmp_path):
    def reset_mocks():
        mock_generate.reset_mock()
        mock_assign.reset_mock()

    profiles = [
        PatientProfile(name="P1*", profile="text1"),
        PatientProfile(name="P2!", profile="text2"),
        PatientProfile(name="P3#", profile="text3"),
    ]
    tested = SyntheticChartGenerator(VendorKey("v", "k"), profiles)

    tests = [
        (
            "two valid charts",
            1,
            2,
            [
                Chart(
                    demographic_str="data1",
                    condition_history=[],
                    current_allergies=[],
                    current_conditions=[],
                    current_medications=[],
                    current_goals=[],
                    family_history=[],
                    surgery_history=[],
                ),
                Chart(
                    demographic_str="data2",
                    condition_history=[],
                    current_allergies=[],
                    current_conditions=[],
                    current_medications=[],
                    current_goals=[],
                    family_history=[],
                    surgery_history=[],
                ),
            ],
            [True, True],
            [True, True],
            [profiles[0], profiles[1]],
            2,
        ),
        (
            "one valid then one invalid",
            2,
            2,
            [
                Chart(
                    demographic_str="data3",
                    condition_history=[],
                    current_allergies=[],
                    current_conditions=[],
                    current_medications=[],
                    current_goals=[],
                    family_history=[],
                    surgery_history=[],
                ),
                Chart(
                    demographic_str="data4",
                    condition_history=[],
                    current_allergies=[],
                    current_conditions=[],
                    current_medications=[],
                    current_goals=[],
                    family_history=[],
                    surgery_history=[],
                ),
            ],
            [True, False],
            [True, True],
            [profiles[1], profiles[2]],
            2,
        ),
        (
            "one invalid then one valid",
            1,
            2,
            [
                Chart(
                    demographic_str="data5",
                    condition_history=[],
                    current_allergies=[],
                    current_conditions=[],
                    current_medications=[],
                    current_goals=[],
                    family_history=[],
                    surgery_history=[],
                ),
                Chart(
                    demographic_str="data6",
                    condition_history=[],
                    current_allergies=[],
                    current_conditions=[],
                    current_medications=[],
                    current_goals=[],
                    family_history=[],
                    surgery_history=[],
                ),
            ],
            [False, True],
            [True, True],
            [profiles[0], profiles[1]],
            2,
        ),
    ]

    for i, (
        test_name,
        start,
        limit,
        charts,
        validate_results,
        expected_files_exist,
        expected_generate_profiles,
        expected_assign_count,
    ) in enumerate(tests):
        mock_generate.side_effect = charts
        mock_assign.side_effect = lambda chart: {"assigned": chart["demographicStr"]}

        output_dir = tmp_path / f"test{i + 1}"
        tested.run_range(start, limit, output_dir)

        # Check file existence
        profile_names = [profile.name for profile in expected_generate_profiles]
        safe_names = [
            profile_name.replace("*", "_").replace("!", "_").replace("#", "_") for profile_name in profile_names
        ]

        for j, (safe_name, should_exist) in enumerate(zip(safe_names, expected_files_exist)):
            output_file = output_dir / safe_name / "limited_chart.json"
            if should_exist:
                assert output_file.exists()
            else:
                assert not output_file.exists()

        # Check mock calls
        expected_generate_calls = [call(profile) for profile in expected_generate_profiles]
        assert mock_generate.mock_calls == expected_generate_calls

        charts_json = [chart.to_json() for chart in charts]
        expected_assign_calls = [call(chart_json) for chart_json in charts_json]
        assert mock_assign.mock_calls == expected_assign_calls
        assert len(mock_assign.mock_calls) == expected_assign_count

        reset_mocks()


def test_main(tmp_path):
    dummy_settings = MagicMock(llm_text=VendorKey(vendor="test", api_key="MY_API_KEY"))

    profiles_file = tmp_path / "profiles.json"
    example_file = tmp_path / "example.json"
    out_dir = tmp_path / "out"
    profiles_file.write_text(json.dumps({"Alice": "profile"}))
    example_file.write_text(json.dumps({"foo": "bar"}))

    load_calls: list[Path] = []

    def fake_load_json(cls, path: Path):
        load_calls.append(path)
        return json.loads(path.read_text())

    run_calls: dict[str, Any] = {}

    def fake_run_range(self, start: int, limit: int, output: Path):
        run_calls["instance"] = self
        run_calls["start"] = start
        run_calls["limit"] = limit
        run_calls["output"] = output

    with (
        patch.object(HelperEvaluation, "settings", classmethod(lambda cls: dummy_settings)),
        patch.object(SyntheticChartGenerator, "load_json", classmethod(fake_load_json)),
        patch.object(SyntheticChartGenerator, "run_range", fake_run_range),
        patch.object(
            ArgumentParser,
            "parse_args",
            lambda self: MockClass(input=profiles_file, output=out_dir, start=1, limit=3),
        ),
    ):
        SyntheticChartGenerator.main()

    assert load_calls == [profiles_file]
    instance = run_calls["instance"]
    assert isinstance(instance, SyntheticChartGenerator)
    assert instance.vendor_key.api_key == "MY_API_KEY"
    assert run_calls["start"] == 1
    assert run_calls["limit"] == 3
    assert run_calls["output"] == out_dir
