from hyperscribe.structures.instruction import Instruction


def test_load_from_json():
    tested = Instruction
    result = tested.load_from_json([
        {
            "uuid": "theUuid1",
            "instruction": "theInstruction1",
            "information": "theInformation1",
            "isNew": False,
            "isUpdated": True,
            "audits": ["line1", "line2"],
        },
        {
            "uuid": "theUuid2",
            "instruction": "theInstruction2",
            "information": "theInformation2",
            "isNew": True,
            "isUpdated": False,
            "audits": ["line3"],
        },
        {},
        {
            "uuid": "theUuid3",
            "instruction": "theInstruction3",
            "information": "theInformation3",
            "isNew": False,
            "isUpdated": True,
            "audits": [],
        },
    ])
    expected = [
        Instruction(
            uuid="theUuid1",
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
            audits=["line1", "line2"],
        ),
        Instruction(
            uuid="theUuid2",
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
            audits=["line3"],
        ),
        Instruction(
            uuid="",
            instruction="",
            information="",
            is_new=True,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid="theUuid3",
            instruction="theInstruction3",
            information="theInformation3",
            is_new=False,
            is_updated=True,
            audits=[],
        ),
    ]
    assert result == expected


def test_to_json():
    tested = Instruction(
        uuid="theUuid",
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
    )
    result = tested.to_json()
    expected = {
        "uuid": "theUuid",
        "instruction": "theInstruction",
        "information": "theInformation",
        "isNew": False,
        "isUpdated": False,
    }
    assert expected == result


def test_limited_str():
    tested = Instruction(
        uuid="theUuid",
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
    )
    result = tested.limited_str()
    expected = "theInstruction (theUuid, new/updated: True/True): theInformation"
    assert expected == result
