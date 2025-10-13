import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import patch, call, MagicMock, Mock

from canvas_sdk.v1.data import (
    ChargeDescriptionMaster,
)
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.lab import LabPartnerTest
from django.db.models import Q

from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.charge_description import ChargeDescription
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.immunization_cached import ImmunizationCached
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.medication_cached import MedicationCached


def test___init__():
    tested = LimitedCache()
    assert tested._actual_staged_commands == []
    assert tested._coded_staged_commands == {}
    assert tested._instance_settings == {}
    assert tested._allergies == []
    assert tested._condition_history == []
    assert tested._conditions == []
    assert tested._demographic == ""
    assert tested._family_history == []
    assert tested._goals == []
    assert tested._immunizations == []
    assert tested._medications == []
    assert tested._note_type == []
    assert tested._preferred_lab_partner == CodedItem(uuid="", label="", code="")
    assert tested._reason_for_visit == []
    assert tested._roles == []
    assert tested._staff_members == []
    assert tested._surgery_history == []
    assert tested._task_labels == []
    assert tested._teams == []
    assert tested._charge_descriptions == []
    assert tested._lab_tests == {}
    assert tested._local_data is False


def test_is_local_data():
    for is_local_data in [True, False]:
        tested = LimitedCache()
        tested._local_data = is_local_data
        assert tested.is_local_data is is_local_data


def test_current_commands():
    tested = LimitedCache()
    result = tested.current_commands()
    assert result == []

    commands = [
        Command(id="id1"),
        Command(id="id2"),
    ]

    tested._actual_staged_commands = commands
    result = tested.current_commands()
    assert result == commands


@patch.object(sqlite3, "connect")
@patch.object(LabPartnerTest, "objects")
def test_lab_tests(lab_test_db, sqlite3_connect):
    chatter = MagicMock()
    connection = MagicMock()

    def reset_mocks():
        lab_test_db.reset_mock()
        sqlite3_connect.reset_mock()
        chatter.reset_mock()
        connection.reset_mock()

    lab_tests = [
        LabPartnerTest(order_code="code123", order_name="labelA"),
        LabPartnerTest(order_code="code369", order_name="labelB"),
        LabPartnerTest(order_code="code752", order_name="labelC"),
    ]
    expected = [
        CodedItem(code="code123", label="labelA", uuid=""),
        CodedItem(code="code369", label="labelB", uuid=""),
        CodedItem(code="code752", label="labelC", uuid=""),
    ]

    # not local
    sqlite3_connect.return_value.__enter__.side_effect = [connection]
    connection.cursor.return_value.fetchall.side_effect = []
    tested = LimitedCache()
    tested._local_data = False
    # -- word1 word2 word3
    lab_test_db.filter.return_value.filter.side_effect = [lab_tests]
    result = tested.lab_tests("theLabPartner", ["word2", "word3", "word1"])
    assert result == expected

    calls = [
        call.filter(lab_partner__name="theLabPartner"),
        call.filter().filter(
            Q(("keywords__icontains", "word2"), ("keywords__icontains", "word3"), ("keywords__icontains", "word1")),
        ),
    ]
    assert lab_test_db.mock_calls == calls
    assert sqlite3_connect.mock_calls == []
    reset_mocks()
    # -- -- repeat with different orders
    result = tested.lab_tests("theLabPartner", ["word1", "word3", "word2"])
    assert result == expected
    assert lab_test_db.mock_calls == []
    assert sqlite3_connect.mock_calls == []
    assert connection.mock_calls == []
    reset_mocks()
    result = tested.lab_tests("theLabPartner", ["word2", "word1", "word3"])
    assert result == expected
    assert lab_test_db.mock_calls == []
    assert sqlite3_connect.mock_calls == []
    assert connection.mock_calls == []
    reset_mocks()
    # -- word1 word2
    lab_test_db.filter.return_value.filter.side_effect = [lab_tests]
    result = tested.lab_tests("theLabPartner", ["word2", "word1"])
    assert result == expected

    calls = [
        call.filter(lab_partner__name="theLabPartner"),
        call.filter().filter(Q(("keywords__icontains", "word2"), ("keywords__icontains", "word1"))),
    ]
    assert lab_test_db.mock_calls == calls
    assert sqlite3_connect.mock_calls == []
    assert connection.mock_calls == []
    reset_mocks()
    # -- -- repeat with different orders
    result = tested.lab_tests("theLabPartner", ["word1", "word2"])
    assert result == expected
    assert lab_test_db.mock_calls == []
    assert sqlite3_connect.mock_calls == []
    assert connection.mock_calls == []
    reset_mocks()

    # local
    sqlite3_connect.return_value.__enter__.side_effect = [connection]
    connection.cursor.return_value.fetchall.side_effect = [
        [
            {"dbid": 456, "order_code": "code123", "order_name": "labelA"},
            {"dbid": 458, "order_code": "code369", "order_name": "labelB"},
            {"dbid": 486, "order_code": "code752", "order_name": "labelC"},
        ],
    ]
    tested = LimitedCache()
    tested._local_data = True

    result = tested.lab_tests("theLabPartner", ["word1", "word3", "word2"])
    assert result == expected
    assert lab_test_db.mock_calls == []
    directory = Path(__file__).parent.as_posix().replace("/tests", "")
    calls = [call(Path(f"{directory}/generic_lab_tests.db")), call().__enter__(), call().__exit__(None, None, None)]
    assert sqlite3_connect.mock_calls == calls
    calls = [
        call.cursor(),
        call.cursor().execute(
            "SELECT `dbid`, `order_code`, `order_name` "
            "FROM `generic_lab_test` WHERE 1=1 "
            " AND `keywords` LIKE :kw_00"
            " AND `keywords` LIKE :kw_01"
            " AND `keywords` LIKE :kw_02 "
            "ORDER BY `dbid`",
            {"kw_00": "%word1%", "kw_01": "%word3%", "kw_02": "%word2%"},
        ),
        call.cursor().fetchall(),
    ]
    assert connection.mock_calls == calls
    reset_mocks()
    # -- -- repeat with different orders
    result = tested.lab_tests("theLabPartner", ["word1", "word3", "word2"])
    assert result == expected
    assert lab_test_db.mock_calls == []
    assert sqlite3_connect.mock_calls == []
    assert connection.mock_calls == []
    reset_mocks()


def test_charge_descriptions():
    charge_descriptions = [
        ChargeDescriptionMaster(cpt_code="code123", name="theFullNameA", short_name="theShortNameA"),
        ChargeDescriptionMaster(cpt_code="code369", name="theFullNameB", short_name="theShortNameB"),
    ]
    tested = LimitedCache()
    result = tested.charge_descriptions()
    assert result == []

    commands = [
        Command(id="id1"),
        Command(id="id2"),
    ]

    tested._charge_descriptions = charge_descriptions
    result = tested.charge_descriptions()
    assert result == charge_descriptions


def test_add_instructions_as_staged_commands():
    schema_key2instruction = {
        "keyA": "theInstruction0",
        "keyB": "theInstruction1",
        "keyC": "theInstruction2",
        "keyD": "theInstruction3",
        "keyE": "theInstruction4",
        "keyF": "theInstruction5",
    }
    instructions = [
        Instruction(
            uuid=f"uuid{idx}",
            index=idx,
            instruction=f"theInstruction{idx // 2}",
            information=f"theInformation{idx}",
            is_new=False,
            is_updated=True,
        )
        for idx in range(5)
    ]

    # no staged commands
    tested = LimitedCache()
    tested.add_instructions_as_staged_commands(instructions, schema_key2instruction)
    expected = {
        "keyA": [
            CodedItem(uuid="uuid0", label="theInformation0", code=""),
            CodedItem(uuid="uuid1", label="theInformation1", code=""),
        ],
        "keyB": [
            CodedItem(uuid="uuid2", label="theInformation2", code=""),
            CodedItem(uuid="uuid3", label="theInformation3", code=""),
        ],
        "keyC": [CodedItem(uuid="uuid4", label="theInformation4", code="")],
    }
    assert tested._coded_staged_commands == expected

    # some staged commands
    tested = LimitedCache()
    tested._coded_staged_commands = {
        "keyA": [
            CodedItem(uuid="uuid1", label="theInitial1", code="theCode1"),
            CodedItem(uuid="uuid6", label="theInitial6", code="theCode6"),
        ],
        "keyB": [CodedItem(uuid="uuid2", label="theInitial2", code="theCode2")],
        "keyC": [CodedItem(uuid="uuid5", label="theInitial5", code="theCode5")],
        "keyD": [CodedItem(uuid="uuid7", label="theInitial4", code="theCode4")],
    }

    tested.add_instructions_as_staged_commands(instructions, schema_key2instruction)
    expected = {
        "keyA": [
            CodedItem(uuid="uuid1", label="theInformation1", code="theCode1"),
            CodedItem(uuid="uuid6", label="theInitial6", code="theCode6"),
            CodedItem(uuid="uuid0", label="theInformation0", code=""),
        ],
        "keyB": [
            CodedItem(uuid="uuid2", label="theInformation2", code="theCode2"),
            CodedItem(uuid="uuid3", label="theInformation3", code=""),
        ],
        "keyC": [
            CodedItem(uuid="uuid5", label="theInitial5", code="theCode5"),
            CodedItem(uuid="uuid4", label="theInformation4", code=""),
        ],
        "keyD": [CodedItem(uuid="uuid7", label="theInitial4", code="theCode4")],
    }

    assert tested._coded_staged_commands == expected


def test_staged_commands_of():
    coded_items = [
        CodedItem(code="code1", label="label1", uuid="uuid1"),
        CodedItem(code="code3", label="label3", uuid="uuid3"),
        CodedItem(code="code2", label="label2", uuid="uuid2"),
    ]

    tested = LimitedCache()
    tested._coded_staged_commands = {
        "keyX": [coded_items[0]],
        "keyY": [],
        "keyZ": [coded_items[1], coded_items[2]],
    }

    tests = [
        (["keyX"], coded_items[:1]),
        (["keyY"], []),
        (["keyZ"], coded_items[1:]),
        (["keyX", "keyY"], coded_items[:1]),
        (["keyX", "keyZ"], coded_items),
    ]
    for keys, expected in tests:
        result = tested.staged_commands_of(keys)
        assert result == expected


def test_staged_commands_as_instructions():
    coded_items = [
        CodedItem(code="code1", label="label1", uuid="uuid1"),
        CodedItem(code="code3", label="label3", uuid="uuid3"),
        CodedItem(code="code2", label="label2", uuid="uuid2"),
    ]

    tested = LimitedCache()
    tested._coded_staged_commands = {
        "keyX": [coded_items[0]],
        "keyY": [],
        "keyZ": [coded_items[1], coded_items[2]],
    }

    schema_key2instruction = {"keyX": "Instruction1", "keyY": "Instruction2", "keyZ": "Instruction3"}
    result = tested.staged_commands_as_instructions(schema_key2instruction)
    expected = Instruction.load_from_json(
        [
            {
                "uuid": "uuid1",
                "instruction": "Instruction1",
                "information": "label1",
                "isNew": True,
                "isUpdated": False,
            },
            {
                "uuid": "uuid3",
                "instruction": "Instruction3",
                "information": "label3",
                "isNew": True,
                "isUpdated": False,
            },
            {
                "uuid": "uuid2",
                "instruction": "Instruction3",
                "information": "label2",
                "isNew": True,
                "isUpdated": False,
            },
        ],
    )
    assert result == expected


def test_current_goals():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._goals = items
    result = tested.current_goals()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_current_conditions():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._conditions = items
    result = tested.current_conditions()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_current_medications():
    items = [Mock(spec=MedicationCached), Mock(spec=MedicationCached)]
    tested = LimitedCache()
    tested._medications = items
    result = tested.current_medications()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_current_immunizations():
    items = [Mock(spec=ImmunizationCached), Mock(spec=ImmunizationCached)]
    tested = LimitedCache()
    tested._immunizations = items
    result = tested.current_immunizations()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_current_allergies():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._allergies = items
    result = tested.current_allergies()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_family_history():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._family_history = items
    result = tested.family_history()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_condition_history():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._condition_history = items
    result = tested.condition_history()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_surgery_history():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._surgery_history = items
    result = tested.surgery_history()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_existing_note_types():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._note_type = items
    result = tested.existing_note_types()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_existing_reason_for_visits():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._reason_for_visit = items
    result = tested.existing_reason_for_visits()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_existing_roles():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._roles = items
    result = tested.existing_roles()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_existing_staff_members():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._staff_members = items
    result = tested.existing_staff_members()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_existing_task_labels():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._task_labels = items
    result = tested.existing_task_labels()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_existing_teams():
    items = [Mock(spec=CodedItem), Mock(spec=CodedItem)]
    tested = LimitedCache()
    tested._teams = items
    result = tested.existing_teams()
    assert result == items

    for item in items:
        assert item.mock_calls == []


def test_demographic__str__():
    tested = LimitedCache()
    tested._demographic = "theDemographic"
    result = tested.demographic__str__()
    assert result == "theDemographic"


def test_practice_setting():
    items = {
        "setting1": Mock(spec=CodedItem),
        "setting2": Mock(spec=CodedItem),
    }
    tested = LimitedCache()
    tested._instance_settings = items
    result = tested.practice_setting("setting1")
    assert result == items["setting1"]
    result = tested.practice_setting("setting2")
    assert result == items["setting2"]

    for item in items.values():
        assert item.mock_calls == []


def test_preferred_lab_partner():
    item = Mock(spec=CodedItem)
    tested = LimitedCache()
    tested._preferred_lab_partner = item
    result = tested.preferred_lab_partner()
    assert result == item

    assert item.mock_calls == []


@patch.object(LimitedCache, "charge_descriptions")
@patch.object(LimitedCache, "surgery_history")
@patch.object(LimitedCache, "preferred_lab_partner")
@patch.object(LimitedCache, "family_history")
@patch.object(LimitedCache, "existing_teams")
@patch.object(LimitedCache, "existing_task_labels")
@patch.object(LimitedCache, "existing_staff_members")
@patch.object(LimitedCache, "existing_roles")
@patch.object(LimitedCache, "existing_reason_for_visits")
@patch.object(LimitedCache, "existing_note_types")
@patch.object(LimitedCache, "current_medications")
@patch.object(LimitedCache, "current_immunizations")
@patch.object(LimitedCache, "current_goals")
@patch.object(LimitedCache, "current_conditions")
@patch.object(LimitedCache, "current_allergies")
@patch.object(LimitedCache, "condition_history")
@patch.object(LimitedCache, "demographic__str__")
@patch.object(LimitedCache, "practice_setting")
def test_to_json(
    practice_setting,
    demographic,
    condition_history,
    current_allergies,
    current_conditions,
    current_goals,
    current_immunizations,
    current_medications,
    existing_note_types,
    existing_reason_for_visits,
    existing_roles,
    existing_staff_members,
    existing_task_labels,
    existing_teams,
    family_history,
    preferred_lab_partner,
    surgery_history,
    charge_descriptions,
):
    def reset_mocks():
        practice_setting.reset_mock()
        demographic.reset_mock()
        condition_history.reset_mock()
        current_allergies.reset_mock()
        current_conditions.reset_mock()
        current_goals.reset_mock()
        current_immunizations.reset_mock()
        current_medications.reset_mock()
        existing_note_types.reset_mock()
        existing_reason_for_visits.reset_mock()
        existing_roles.reset_mock()
        existing_staff_members.reset_mock()
        existing_task_labels.reset_mock()
        existing_teams.reset_mock()
        family_history.reset_mock()
        preferred_lab_partner.reset_mock()
        surgery_history.reset_mock()
        charge_descriptions.reset_mock()

    tested = LimitedCache()
    tested._lab_tests = {
        "word1 word2 word3": [
            CodedItem(uuid="uuid054", label="label054", code="code054"),
            CodedItem(uuid="uuid154", label="label154", code="code154"),
        ],
        "word1 word2": [CodedItem(uuid="uuid157", label="label157", code="code157")],
    }

    tested._coded_staged_commands = {
        "keyX": [CodedItem(code="code1", label="label1", uuid="uuid1")],
        "keyY": [],
        "keyZ": [
            CodedItem(code="code3", label="label3", uuid="uuid3"),
            CodedItem(code="code2", label="label2", uuid="uuid2"),
        ],
    }
    practice_setting.side_effect = ["thePreferredLabPartner", "theServiceAreaZipCodes"]
    demographic.side_effect = ["theDemographic"]
    condition_history.side_effect = [
        [
            CodedItem(uuid="uuid002", label="label002", code="code002"),
            CodedItem(uuid="uuid102", label="label102", code="code102"),
        ],
    ]
    current_allergies.side_effect = [
        [
            CodedItem(uuid="uuid003", label="label003", code="code003"),
            CodedItem(uuid="uuid103", label="label103", code="code103"),
        ],
    ]
    current_conditions.side_effect = [
        [
            CodedItem(uuid="uuid004", label="label004", code="code004"),
            CodedItem(uuid="uuid104", label="label104", code="code104"),
        ],
    ]
    current_goals.side_effect = [
        [
            CodedItem(uuid="uuid005", label="label005", code="code005"),
            CodedItem(uuid="uuid105", label="label105", code="code105"),
        ],
    ]
    current_immunizations.side_effect = [
        [
            ImmunizationCached(
                uuid="uuid321",
                label="label321",
                code_cpt="codeCpt321",
                code_cvx="codeCvx321",
                comments="theComments321",
                approximate_date=date(2025, 7, 21),
            ),
            ImmunizationCached(
                uuid="uuid323",
                label="label323",
                code_cpt="codeCpt323",
                code_cvx="codeCvx323",
                comments="theComments323",
                approximate_date=date(2025, 7, 23),
            ),
        ],
    ]
    current_medications.side_effect = [
        [
            MedicationCached(
                uuid="uuid076",
                label="label076",
                code_rx_norm="code076",
                code_fdb="code987",
                national_drug_code="ndc12",
                potency_unit_code="puc78",
            ),
            MedicationCached(
                uuid="uuid176",
                label="label176",
                code_rx_norm="code176",
                code_fdb="code998",
                national_drug_code="ndc17",
                potency_unit_code="puc56",
            ),
        ],
    ]
    existing_note_types.side_effect = [
        [
            CodedItem(uuid="uuid007", label="label007", code="code007"),
            CodedItem(uuid="uuid107", label="label107", code="code107"),
        ],
    ]
    existing_reason_for_visits.side_effect = [
        [
            CodedItem(uuid="uuid009", label="label009", code="code009"),
            CodedItem(uuid="uuid109", label="label109", code="code109"),
        ],
    ]
    existing_roles.side_effect = [
        [
            CodedItem(uuid="uuid431", label="label431", code="code431"),
            CodedItem(uuid="uuid473", label="label473", code="code473"),
        ],
    ]
    existing_staff_members.side_effect = [
        [
            CodedItem(uuid="uuid037", label="label037", code="code037"),
            CodedItem(uuid="uuid137", label="label137", code="code137"),
        ],
    ]
    existing_task_labels.side_effect = [
        [
            CodedItem(uuid="uuid091", label="label091", code="code091"),
            CodedItem(uuid="uuid191", label="label191", code="code191"),
        ],
    ]
    existing_teams.side_effect = [
        [
            CodedItem(uuid="uuid894", label="label894", code="code894"),
            CodedItem(uuid="uuid873", label="label873", code="code873"),
        ],
    ]
    family_history.side_effect = [
        [
            CodedItem(uuid="uuid010", label="label010", code="code010"),
            CodedItem(uuid="uuid110", label="label110", code="code110"),
        ],
    ]
    preferred_lab_partner.side_effect = [CodedItem(uuid="theUuid", label="theLabel", code="theCode")]
    surgery_history.side_effect = [
        [
            CodedItem(uuid="uuid011", label="label011", code="code011"),
            CodedItem(uuid="uuid111", label="label111", code="code111"),
        ],
    ]

    charge_descriptions.side_effect = [
        [
            ChargeDescription(short_name="shortName1", full_name="fullName1", cpt_code="code1"),
            ChargeDescription(short_name="shortName2", full_name="fullName2", cpt_code="code2"),
        ],
    ]

    result = tested.to_json()
    expected = {
        "conditionHistory": [
            {"code": "code002", "label": "label002", "uuid": "uuid002"},
            {"code": "code102", "label": "label102", "uuid": "uuid102"},
        ],
        "currentAllergies": [
            {"code": "code003", "label": "label003", "uuid": "uuid003"},
            {"code": "code103", "label": "label103", "uuid": "uuid103"},
        ],
        "currentConditions": [
            {"code": "code004", "label": "label004", "uuid": "uuid004"},
            {"code": "code104", "label": "label104", "uuid": "uuid104"},
        ],
        "currentGoals": [
            {"code": "code005", "label": "label005", "uuid": "uuid005"},
            {"code": "code105", "label": "label105", "uuid": "uuid105"},
        ],
        "currentImmunization": [
            {
                "approximateDate": "2025-07-21",
                "codeCpt": "codeCpt321",
                "codeCvx": "codeCvx321",
                "comments": "theComments321",
                "label": "label321",
                "uuid": "uuid321",
            },
            {
                "approximateDate": "2025-07-23",
                "codeCpt": "codeCpt323",
                "codeCvx": "codeCvx323",
                "comments": "theComments323",
                "label": "label323",
                "uuid": "uuid323",
            },
        ],
        "currentMedications": [
            {
                "codeRxNorm": "code076",
                "label": "label076",
                "uuid": "uuid076",
                "codeFdb": "code987",
                "nationalDrugCode": "ndc12",
                "potencyUnitCode": "puc78",
            },
            {
                "codeRxNorm": "code176",
                "label": "label176",
                "uuid": "uuid176",
                "codeFdb": "code998",
                "nationalDrugCode": "ndc17",
                "potencyUnitCode": "puc56",
            },
        ],
        "demographicStr": "theDemographic",
        "existingNoteTypes": [
            {"code": "code007", "label": "label007", "uuid": "uuid007"},
            {"code": "code107", "label": "label107", "uuid": "uuid107"},
        ],
        "existingReasonForVisit": [
            {"code": "code009", "label": "label009", "uuid": "uuid009"},
            {"code": "code109", "label": "label109", "uuid": "uuid109"},
        ],
        "existingRoles": [
            {"code": "code431", "label": "label431", "uuid": "uuid431"},
            {"code": "code473", "label": "label473", "uuid": "uuid473"},
        ],
        "existingStaffMembers": [
            {"code": "code037", "label": "label037", "uuid": "uuid037"},
            {"code": "code137", "label": "label137", "uuid": "uuid137"},
        ],
        "existingTeams": [
            {"code": "code894", "label": "label894", "uuid": "uuid894"},
            {"code": "code873", "label": "label873", "uuid": "uuid873"},
        ],
        "existingTaskLabels": [
            {"code": "code091", "label": "label091", "uuid": "uuid091"},
            {"code": "code191", "label": "label191", "uuid": "uuid191"},
        ],
        "familyHistory": [
            {"code": "code010", "label": "label010", "uuid": "uuid010"},
            {"code": "code110", "label": "label110", "uuid": "uuid110"},
        ],
        "stagedCommands": {
            "keyX": [{"code": "code1", "label": "label1", "uuid": "uuid1"}],
            "keyY": [],
            "keyZ": [
                {"code": "code3", "label": "label3", "uuid": "uuid3"},
                {"code": "code2", "label": "label2", "uuid": "uuid2"},
            ],
        },
        "surgeryHistory": [
            {"code": "code011", "label": "label011", "uuid": "uuid011"},
            {"code": "code111", "label": "label111", "uuid": "uuid111"},
        ],
        "chargeDescriptions": [
            {"fullName": "fullName1", "shortName": "shortName1", "cptCode": "code1"},
            {"fullName": "fullName2", "shortName": "shortName2", "cptCode": "code2"},
        ],
        "settings": {
            "preferredLabPartner": "thePreferredLabPartner",
            "serviceAreaZipCodes": "theServiceAreaZipCodes",
        },
        "preferredLabPartner": {"uuid": "theUuid", "label": "theLabel", "code": "theCode"},
        "labTests": {},
    }

    assert result == expected

    calls = [
        call("preferredLabPartner"),
        call("serviceAreaZipCodes"),
    ]
    assert practice_setting.mock_calls == calls
    calls = [call()]
    assert demographic.mock_calls == calls
    assert condition_history.mock_calls == calls
    assert current_allergies.mock_calls == calls
    assert current_conditions.mock_calls == calls
    assert current_goals.mock_calls == calls
    assert current_immunizations.mock_calls == calls
    assert current_medications.mock_calls == calls
    assert existing_note_types.mock_calls == calls
    assert existing_reason_for_visits.mock_calls == calls
    assert existing_roles.mock_calls == calls
    assert existing_staff_members.mock_calls == calls
    assert existing_task_labels.mock_calls == calls
    assert existing_teams.mock_calls == calls
    assert family_history.mock_calls == calls
    assert preferred_lab_partner.mock_calls == calls
    assert surgery_history.mock_calls == calls
    assert charge_descriptions.mock_calls == calls
    reset_mocks()
