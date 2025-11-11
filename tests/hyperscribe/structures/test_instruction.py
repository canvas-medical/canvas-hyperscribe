from hyperscribe.structures.instruction import Instruction


def test_load_from_json():
    tested = Instruction
    result = tested.load_from_json(
        [
            {
                "uuid": "theUuid1",
                "index": 0,
                "instruction": "theInstruction1",
                "information": "theInformation1",
                "isNew": False,
                "isUpdated": True,
            },
            {
                "uuid": "theUuid2",
                "index": 1,
                "instruction": "theInstruction2",
                "information": "theInformation2",
                "isNew": True,
                "isUpdated": False,
            },
            {},
            {
                "uuid": "theUuid3",
                "index": 2,
                "instruction": "theInstruction3",
                "information": "theInformation3",
                "isNew": False,
                "isUpdated": True,
            },
        ],
    )
    expected = [
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="",
            index=0,
            instruction="",
            information="",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid3",
            index=2,
            instruction="theInstruction3",
            information="theInformation3",
            is_new=False,
            is_updated=True,
            previous_information="",
        ),
    ]
    assert result == expected


def test_to_json():
    for flag in [True, False]:
        tested = Instruction(
            uuid="theUuid",
            index=3,
            instruction="theInstruction",
            information="theInformation",
            is_new=flag,
            is_updated=flag,
            previous_information="",
        )
        result = tested.to_json(True)
        expected = {
            "uuid": "theUuid",
            "index": 3,
            "instruction": "theInstruction",
            "information": "theInformation",
            "isNew": False,
            "isUpdated": False,
        }
        assert expected == result
        result = tested.to_json(False)
        expected = {
            "uuid": "theUuid",
            "index": 3,
            "instruction": "theInstruction",
            "information": "theInformation",
            "isNew": flag,
            "isUpdated": flag,
        }
        assert expected == result


def test_limited_str():
    tested = Instruction(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="",
    )
    result = tested.limited_str()
    expected = "theInstruction #07 (theUuid, new/updated: True/True): theInformation"
    assert expected == result


def test___eq__():
    tested = Instruction(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="thePreviousInformation",
    )
    tests = [
        (
            Instruction(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
            ),
            True,
        ),
        (
            Instruction(
                uuid="otherUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
            ),
            False,
        ),
        (
            Instruction(
                uuid="theUuid",
                index=3,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
            ),
            False,
        ),
        (
            Instruction(
                uuid="theUuid",
                index=7,
                instruction="otherInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
            ),
            False,
        ),
        (
            Instruction(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="otherInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
            ),
            False,
        ),
        (
            Instruction(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=False,
                is_updated=True,
                previous_information="thePreviousInformation",
            ),
            False,
        ),
        (
            Instruction(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=False,
                previous_information="thePreviousInformation",
            ),
            False,
        ),
        (
            Instruction(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="otherPreviousInformation",
            ),
            False,
        ),
    ]
    for other, expected in tests:
        if expected:
            assert tested == other
        else:
            assert tested != other
        assert tested is not other
