import hashlib
import pytest
from evaluations.case_builders.synthetic_profile_generator_prompts import SyntheticProfileGeneratorPrompts


def test_get_prompts():
    tested = SyntheticProfileGeneratorPrompts
    tests = [
        (
            "med_management",
            1,
            2,
            {"expected": "schema"},
            [],
            False,
            None,
            "4812ff261353bfc9054ffb110df4234a",
            "03dbc5a556ba0029dd3cdd61c49c86ac",
        ),
        (
            "primary_care",
            2,
            3,
            {"expected": "schema"},
            ["Routine checkup"],
            False,
            None,
            "cb7b9676d49a9378ad495d57f5a18426",
            "7fdd9f10925610cc4082dd25c0665bb4",
        ),
        (
            "serious_mental_illness",
            1,
            4,
            {"expected": "schema"},
            [],
            False,
            None,
            "3dff218b368fe713cf9f7d44b852fce4",
            "e2dc66a48d6efd87e0983230de956c03",
        ),
        (
            "unknown_category",
            1,
            2,
            {"expected": "schema"},
            [],
            True,
            "Unknown category: unknown_category. Supported: med_management, primary_care, serious_mental_illness",
            None,
            None,
        ),
    ]

    for (
        category,
        batch_num,
        count,
        schema,
        seen_scenarios,
        should_raise,
        expected_error,
        expected_system_md5,
        expected_user_md5,
    ) in tests:
        if should_raise:
            with pytest.raises(ValueError) as exc_info:
                tested.get_prompts(category, batch_num, count, schema, seen_scenarios)
            assert str(exc_info.value) == expected_error
        else:
            result = tested.get_prompts(category, batch_num, count, schema, seen_scenarios)
            assert isinstance(result, tuple)

            system_prompt, user_prompt = result
            assert isinstance(system_prompt, list)
            assert isinstance(user_prompt, list)
            assert len(system_prompt) > 0
            assert len(user_prompt) > 0

            # MD5 validation instead of calling implementation
            result_system_md5 = hashlib.md5("\n".join(system_prompt).encode()).hexdigest()
            result_user_md5 = hashlib.md5("\n".join(user_prompt).encode()).hexdigest()

            assert result_system_md5 == expected_system_md5
            assert result_user_md5 == expected_user_md5


def test_med_management_prompts():
    tested = SyntheticProfileGeneratorPrompts

    tests = [
        # (batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5)
        (2, 3, {"expected": "schema"}, [], "4812ff261353bfc9054ffb110df4234a", "35e9db9a1a868a720c679f3c0921fa8b"),
        (
            1,
            5,
            {"expected": "schema"},
            ["First scenario"],
            "4812ff261353bfc9054ffb110df4234a",
            "50570a002036340c13ed81cecdb2e669",
        ),
        (
            3,
            2,
            {"expected": "schema"},
            ["ACE-inhibitor cough", "warfarin drift"],
            "4812ff261353bfc9054ffb110df4234a",
            "d7c45457d6acf3eb6a1b410f39d80d03",
        ),
    ]

    for batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5 in tests:
        result = tested.med_management_prompts(batch_num, count, schema, seen_scenarios)
        expected = tuple
        assert isinstance(result, expected)

        system_prompt, user_prompt = result
        assert isinstance(system_prompt, list)
        assert isinstance(user_prompt, list)
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0

        # md5
        result_system_md5 = hashlib.md5("\n".join(system_prompt).encode()).hexdigest()
        result_user_md5 = hashlib.md5("\n".join(user_prompt).encode()).hexdigest()

        assert result_system_md5 == expected_system_md5
        assert result_user_md5 == expected_user_md5


def test_primary_care_prompts():
    tested = SyntheticProfileGeneratorPrompts

    tests = [
        # (batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5)
        (2, 3, {"expected": "schema"}, [], "cb7b9676d49a9378ad495d57f5a18426", "e2bed1f3ef615e58fdcf0e9a5e98e6dc"),
        (
            1,
            4,
            {"expected": "schema"},
            ["Diabetes screening"],
            "cb7b9676d49a9378ad495d57f5a18426",
            "d24a48b49623a33b097a1ec6a52bef89",
        ),
        (
            2,
            2,
            {"expected": "schema"},
            ["Routine checkup", "Colonoscopy"],
            "cb7b9676d49a9378ad495d57f5a18426",
            "abf54f5b3c6d0ba3927130a2b2c60591",
        ),
    ]

    for batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5 in tests:
        result = tested.primary_care_prompts(batch_num, count, schema, seen_scenarios)
        assert isinstance(result, tuple)

        system_prompt, user_prompt = result
        assert isinstance(system_prompt, list)
        assert isinstance(user_prompt, list)
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0

        # md5
        result_system_md5 = hashlib.md5("\n".join(system_prompt).encode()).hexdigest()
        result_user_md5 = hashlib.md5("\n".join(user_prompt).encode()).hexdigest()

        assert result_system_md5 == expected_system_md5
        assert result_user_md5 == expected_user_md5


def test_serious_mental_illness_prompts():
    tested = SyntheticProfileGeneratorPrompts

    tests = [
        # (batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5)
        (2, 3, {"expected": "schema"}, [], "3dff218b368fe713cf9f7d44b852fce4", "afcc988352d5a7dfdbe31f49584a280f"),
        (
            1,
            3,
            {"expected": "schema"},
            ["Medication adherence"],
            "3dff218b368fe713cf9f7d44b852fce4",
            "3476f6758ef3ff30ec5c2b1871d424a2",
        ),
        (
            3,
            4,
            {"expected": "schema"},
            ["Crisis episode", "Housing instability"],
            "3dff218b368fe713cf9f7d44b852fce4",
            "29b020e5ca97e0f43623b8c0f71f839a",
        ),
    ]

    for batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5 in tests:
        result = tested.serious_mental_illness_prompts(batch_num, count, schema, seen_scenarios)
        expected = tuple
        assert isinstance(result, expected)

        system_prompt, user_prompt = result
        assert isinstance(system_prompt, list)
        assert isinstance(user_prompt, list)
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0

        # md5
        result_system_md5 = hashlib.md5("\n".join(system_prompt).encode()).hexdigest()
        result_user_md5 = hashlib.md5("\n".join(user_prompt).encode()).hexdigest()

        assert result_system_md5 == expected_system_md5
        assert result_user_md5 == expected_user_md5
