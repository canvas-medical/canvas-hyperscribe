from hyperscribe.structures.instruction import Instruction
from tests.helper import is_constant


def test_constants():
    tested = Instruction
    constants = {
        "CSV_FIELDS": ["uuid", "index", "instruction", "information", "is_new", "is_updated"],
    }
    assert is_constant(tested, constants)


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


def test_load_from_csv():
    tested = Instruction

    # empty csv list
    result = tested.load_from_csv([])
    expected = []
    assert result == expected

    # csv list with header and data
    csv_list = [
        "uuid,index,instruction,information,is_new,is_updated",
        "theUuid1,0,theInstruction1,theInformation1,false,true",
        "theUuid2,1,theInstruction2,theInformation2,true,false",
        '"theUuid3",2,"instruction with, comma","information with, comma",true,true',
    ]
    result = tested.load_from_csv(csv_list)
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
            uuid="theUuid3",
            index=2,
            instruction="instruction with, comma",
            information="information with, comma",
            is_new=True,
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


def test_to_csv():
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
        result = tested.to_csv(True)
        expected = "theUuid,3,theInstruction,theInformation,False,False"
        assert result == expected
        result = tested.to_csv(False)
        expected = f"theUuid,3,theInstruction,theInformation,{flag},{flag}"
        assert result == expected

    # test with special characters
    tested = Instruction(
        uuid="theUuid",
        index=3,
        instruction="instruction with, comma",
        information='information with "quotes"',
        is_new=True,
        is_updated=False,
        previous_information="",
    )
    result = tested.to_csv(False)
    expected = 'theUuid,3,"instruction with, comma","information with ""quotes""",True,False'
    assert result == expected


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


def test_list_to_csv():
    tested = Instruction

    # empty list
    result = tested.list_to_csv([])
    expected = "uuid,index,instruction,information,is_new,is_updated"
    assert result == expected

    # list with instructions
    instructions = [
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="instruction with, comma",
            information='information with "quotes"',
            is_new=False,
            is_updated=True,
            previous_information="",
        ),
    ]
    result = tested.list_to_csv(instructions)
    expected = (
        "uuid,index,instruction,information,is_new,is_updated\n"
        "theUuid1,0,theInstruction1,theInformation1,True,False\n"
        'theUuid2,1,"instruction with, comma","information with ""quotes""",False,True'
    )
    assert result == expected


def test_to_csv_description():
    tested = Instruction
    commands = ["command1", "command2", "command3"]
    result = tested.to_csv_description(commands)
    expected = (
        "uuid,index,instruction,information,is_new,is_updated\n"
        "a unique identifier in this discussion,"
        "the 0-based appearance order of the instruction in this discussion,"
        "one of: 'command1/command2/command3',"
        "all relevant information extracted from the discussion explaining and/or defining the instruction,"
        "the instruction is new to the discussion,"
        "the instruction is an update of an instruction previously identified in the discussion"
    )
    assert result == expected
