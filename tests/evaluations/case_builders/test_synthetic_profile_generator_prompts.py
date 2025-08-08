import hashlib
from evaluations.case_builders.synthetic_profile_generator_prompts import SyntheticProfileGeneratorPrompts


def test_med_management_prompts():
    tested = SyntheticProfileGeneratorPrompts

    tests = [
        # (batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5)
        (2, 3, {"expected": "schema"}, [], "4812ff261353bfc9054ffb110df4234a", "35e9db9a1a868a720c679f3c0921fa8b")
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
        (2, 3, {"expected": "schema"}, [], "cb7b9676d49a9378ad495d57f5a18426", "e2bed1f3ef615e58fdcf0e9a5e98e6dc")
    ]

    for batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5 in tests:
        result = tested.primary_care_prompts(batch_num, count, schema, seen_scenarios)
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


def test_serious_mental_illness_prompts():
    tested = SyntheticProfileGeneratorPrompts

    tests = [
        # (batch_num, count, schema, seen_scenarios, expected_system_md5, expected_user_md5)
        (2, 3, {"expected": "schema"}, [], "3dff218b368fe713cf9f7d44b852fce4", "afcc988352d5a7dfdbe31f49584a280f"),
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
