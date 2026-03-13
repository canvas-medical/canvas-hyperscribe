from hyperscribe.scribe.commands.ap_split import (
    match_condition,
    parse_ap_blocks,
    significant_words,
    split_plan_into_diagnoses,
    word_overlap,
)


# --- parse_ap_blocks ---


def test_parse_ap_blocks_empty() -> None:
    assert parse_ap_blocks("") == []


def test_parse_ap_blocks_none_text() -> None:
    # The function should treat None-ish empty string the same.
    assert parse_ap_blocks("") == []


def test_parse_ap_blocks_single_header_no_body() -> None:
    blocks = parse_ap_blocks("Migraine without aura")
    assert len(blocks) == 1
    assert blocks[0].header == "Migraine without aura"
    assert blocks[0].body == []


def test_parse_ap_blocks_header_with_bullets() -> None:
    text = "Migraine without aura\n- Start sumatriptan 50mg\n- Reduce screen time"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].header == "Migraine without aura"
    assert len(blocks[0].body) == 2
    assert blocks[0].body[0] == "- Start sumatriptan 50mg"
    assert blocks[0].body[1] == "- Reduce screen time"


def test_parse_ap_blocks_multiple_blocks() -> None:
    text = "Migraine without aura\n- Start sumatriptan\n\nHypertension\n- Continue lisinopril\n- Monitor BP"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].header == "Migraine without aura"
    assert blocks[0].body == ["- Start sumatriptan"]
    assert blocks[1].header == "Hypertension"
    assert len(blocks[1].body) == 2


def test_parse_ap_blocks_multiline_header() -> None:
    text = "Migraine without aura\nLikely triggered by stress\n- Start sumatriptan"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].header == "Migraine without aura\nLikely triggered by stress"
    assert blocks[0].body == ["- Start sumatriptan"]


def test_parse_ap_blocks_orphan_bullets() -> None:
    text = "- Something without a header"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].header == ""
    assert blocks[0].body == ["- Something without a header"]


def test_parse_ap_blocks_blank_lines_between() -> None:
    text = "Block1\n\n\nBlock2"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].header == "Block1"
    assert blocks[1].header == "Block2"


def test_parse_ap_blocks_bullet_markers() -> None:
    """Different bullet styles are recognized."""
    text = "Header\n* star bullet\n\u2022 unicode bullet"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert len(blocks[0].body) == 2


# --- significant_words ---


def test_significant_words_filters_stop_words() -> None:
    words = significant_words("the quick brown fox and a lazy dog")
    assert "the" not in words
    assert "and" not in words
    assert "a" not in words
    assert "quick" in words
    assert "brown" in words


def test_significant_words_filters_short() -> None:
    words = significant_words("I am ok")
    assert "i" not in words  # single char after lowering
    assert "am" in words  # 2 chars is ok
    assert "ok" in words


def test_significant_words_strips_punctuation() -> None:
    words = significant_words("Headache, chronic")
    assert "headache" in words
    assert "chronic" in words


# --- word_overlap ---


def test_word_overlap_identical() -> None:
    assert word_overlap("chronic headache", "chronic headache") == 1.0


def test_word_overlap_partial() -> None:
    score = word_overlap("chronic daily headache", "headache disorder")
    assert score > 0.0


def test_word_overlap_no_match() -> None:
    assert word_overlap("migraine", "diabetes mellitus") == 0.0


def test_word_overlap_empty() -> None:
    assert word_overlap("", "something") == 0.0
    assert word_overlap("something", "") == 0.0


# --- match_condition ---


def test_match_condition_exact_substring() -> None:
    conditions = [
        {"display": "Headache", "coding": [{"code": "R51", "display": "Headache"}]},
        {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
    ]
    result = match_condition("Headache", conditions)
    assert result is not None
    assert result["display"] == "Headache"


def test_match_condition_substring_in_coding_display() -> None:
    conditions = [
        {"display": "HTN", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
    ]
    result = match_condition("Essential hypertension, well controlled", conditions)
    assert result is not None
    assert result["display"] == "HTN"


def test_match_condition_header_within_display() -> None:
    conditions = [
        {"display": "Migraine without aura, chronic", "coding": []},
    ]
    result = match_condition("Migraine without aura", conditions)
    assert result is not None


def test_match_condition_word_overlap_pass() -> None:
    conditions = [
        {"display": "Type 2 diabetes mellitus", "coding": [{"code": "E11", "display": "Type 2 diabetes"}]},
    ]
    result = match_condition("Diabetes type 2", conditions)
    assert result is not None


def test_match_condition_no_match() -> None:
    conditions = [
        {"display": "Headache", "coding": [{"code": "R51", "display": "Headache"}]},
    ]
    result = match_condition("Lower back pain", conditions)
    assert result is None


def test_match_condition_empty_conditions() -> None:
    assert match_condition("Headache", []) is None


def test_match_condition_empty_header() -> None:
    conditions = [{"display": "Headache", "coding": []}]
    assert match_condition("", conditions) is None


# --- split_plan_into_diagnoses ---


def test_split_plan_into_diagnoses_basic() -> None:
    commands = [
        {"command_type": "rfv", "data": {"comment": "Pain"}, "section_key": "chief_complaint"},
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Start sumatriptan\n\nHypertension\n- Continue lisinopril"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43.909", "display": "Migraine, unspecified"}]},
            {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 3  # rfv + 2 diagnose
    assert updated[0]["command_type"] == "rfv"
    assert updated[1]["command_type"] == "diagnose"
    assert updated[1]["data"]["icd10_code"] == "G43.909"
    assert updated[1]["data"]["accepted"] is True
    assert updated[2]["command_type"] == "diagnose"
    assert updated[2]["data"]["icd10_code"] == "I10"
    assert unmatched == []


def test_split_plan_into_diagnoses_unmatched() -> None:
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Start sumatriptan"},
            "section_key": "assessment_and_plan",
        },
    ]
    extra_condition = {"display": "Diabetes", "coding": [{"code": "E11", "display": "Type 2 diabetes"}]}
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43.909", "display": "Migraine"}]},
            extra_condition,
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert len(unmatched) == 1
    assert unmatched[0] is extra_condition


def test_split_plan_into_diagnoses_no_plan_command() -> None:
    commands = [
        {"command_type": "rfv", "data": {"comment": "Pain"}, "section_key": "chief_complaint"},
    ]
    updated, unmatched = split_plan_into_diagnoses(commands, {"assessment_and_plan": []})
    assert updated == commands
    assert unmatched == []


def test_split_plan_into_diagnoses_empty_narrative() -> None:
    commands = [
        {"command_type": "plan", "data": {"narrative": ""}, "section_key": "assessment_and_plan"},
    ]
    updated, unmatched = split_plan_into_diagnoses(commands, {"assessment_and_plan": []})
    assert updated == commands
    assert unmatched == []


def test_split_plan_into_diagnoses_no_icd_code() -> None:
    """When a condition has no coding, the diagnose block is created without an ICD code."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Unknown condition\n- Monitor"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions: dict[str, list[dict[str, object]]] = {"assessment_and_plan": []}
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["accepted"] is False


def test_split_plan_preserves_other_commands() -> None:
    """Commands before and after the plan command are preserved."""
    commands = [
        {"command_type": "rfv", "data": {"comment": "Pain"}, "section_key": "chief_complaint"},
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Sumatriptan"},
            "section_key": "assessment_and_plan",
        },
        {"command_type": "hpi", "data": {"narrative": "Headache"}, "section_key": "history_of_present_illness"},
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43", "display": "Migraine"}]},
        ],
    }
    updated, _ = split_plan_into_diagnoses(commands, section_conditions)
    assert updated[0]["command_type"] == "rfv"
    assert updated[1]["command_type"] == "diagnose"
    assert updated[2]["command_type"] == "hpi"


def test_split_plan_uses_plan_section_key() -> None:
    """Works with section_key='plan' as well as 'assessment_and_plan'."""
    commands = [
        {"command_type": "plan", "data": {"narrative": "Headache\n- Rest"}, "section_key": "plan"},
    ]
    section_conditions = {
        "plan": [{"display": "Headache", "coding": [{"code": "R51", "display": "Headache"}]}],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["section_key"] == "plan"
    assert unmatched == []
