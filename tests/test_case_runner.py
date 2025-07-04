from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from case_runner import CaseRunner
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.records.case import Case as RecordCase
from evaluations.structures.records.generated_note import GeneratedNote as RecordGeneratedNote, GeneratedNote
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


@patch("case_runner.ArgumentParser")
def test_parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = CaseRunner
    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested.parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Run the case based on the local settings"),
        call().add_argument("--case_name", type=str, required=True, help="The case to run"),
        call().add_argument("--cycles", type=int, required=True, help="Split the transcript in as many cycles"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("case_runner.AuditorPostgres")
@patch("case_runner.AudioInterpreter")
@patch("case_runner.GeneratedNoteStore")
@patch("case_runner.CaseStore")
@patch("case_runner.HelperEvaluation")
@patch.object(Commander, "transcript2commands")
@patch.object(ImplementedCommands, "schema_key2instruction")
@patch.object(CachedSdk, "get_discussion")
@patch.object(LimitedCache, "load_from_json")
@patch.object(CaseRunner, "parameters")
def test_run(
        parameters,
        load_from_json,
        get_discussion,
        schema_key2instruction,
        transcript2commands,
        helper,
        case_store,
        generated_note_store,
        audio_interpreter,
        auditor_postgres,
):
    mock_chatter = MagicMock()
    mock_settings = MagicMock()
    def reset_mocks():
        parameters.reset_mock()
        load_from_json.reset_mock()
        get_discussion.reset_mock()
        schema_key2instruction.reset_mock()
        transcript2commands.reset_mock()
        helper.reset_mock()
        case_store.reset_mock()
        generated_note_store.reset_mock()
        audio_interpreter.reset_mock()
        auditor_postgres.reset_mock()
        mock_chatter.reset_mock()
        mock_settings.reset_mock()

    identification = IdentificationParameters(
        patient_uuid='_PatientUuid',
        note_uuid='_NoteUuid',
        provider_uuid='_ProviderUuid',
        canvas_instance='runner-environment',
    )
    lines = [
        Line(speaker="theSpeaker1", text="theText1"),
        Line(speaker="theSpeaker2", text="theText2"),
        Line(speaker="theSpeaker3", text="theText3"),
        Line(speaker="theSpeaker4", text="theText4"),
        Line(speaker="theSpeaker5", text="theText5"),
        Line(speaker="theSpeaker6", text="theText6"),
        Line(speaker="theSpeaker7", text="theText7"),
    ]

    # case does not exist
    parameters.side_effect = [Namespace(case_name="theCase", cycles=3)]
    load_from_json.return_value.staged_commands_as_instructions.side_effect = []
    schema_key2instruction.side_effect = []
    transcript2commands.side_effect = []
    helper.settings.side_effect = [mock_settings]
    mock_settings.llm_text.vendor = "theVendor"
    mock_settings.llm_text_model.side_effect = []
    helper.aws_s3_credentials.side_effect = ["theAwsCredentials"]
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    case_store.return_value.get_case.side_effect = [RecordCase(name="theName", id=0)]
    generated_note_store.return_value.insert.side_effect = []
    audio_interpreter.side_effect = []
    mock_chatter.identification = identification

    tested = CaseRunner
    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    assert load_from_json.mock_calls == []
    assert get_discussion.mock_calls == []
    assert schema_key2instruction.mock_calls == []
    assert transcript2commands.mock_calls == []
    calls = [
        call.settings(),
        call.aws_s3_credentials(),
        call.postgres_credentials(),
    ]
    assert helper.mock_calls == calls
    calls = [
        call('thePostgresCredentials'),
        call().get_case('theCase'),
    ]
    assert case_store.mock_calls == calls
    assert generated_note_store.mock_calls == []
    assert audio_interpreter.mock_calls == []
    assert auditor_postgres.mock_calls == []
    assert mock_chatter.mock_calls == []
    assert mock_settings.mock_calls == []
    reset_mocks()

    # case exists
    tests = [
        # less than 1 cycle
        (
            Namespace(case_name="theCase", cycles=0),
            1,
            [
                call(auditor_postgres.return_value, lines[0:7], mock_chatter, ['theCommandAsInstructions']),
            ]
        ),
        # some cycles
        (
            Namespace(case_name="theCase", cycles=3),
            3,
            [
                call(auditor_postgres.return_value, lines[0:3], mock_chatter, ["theCommandAsInstructions"]),
                call(auditor_postgres.return_value, lines[3:6], mock_chatter, ['previous1']),
                call(auditor_postgres.return_value, lines[6:7], mock_chatter, ['previous2']),
            ]
        ),
        (
            Namespace(case_name="theCase", cycles=4),
            4,
            [
                call(auditor_postgres.return_value, lines[0:2], mock_chatter, ["theCommandAsInstructions"]),
                call(auditor_postgres.return_value, lines[2:4], mock_chatter, ['previous1']),
                call(auditor_postgres.return_value, lines[4:6], mock_chatter, ['previous2']),
                call(auditor_postgres.return_value, lines[6:7], mock_chatter, ['previous3']),
            ]
        ),
        # cycles more than the transcript turns
        (
            Namespace(case_name="theCase", cycles=10),
            7,
            [
                call(auditor_postgres.return_value, lines[0:1], mock_chatter, ["theCommandAsInstructions"]),
                call(auditor_postgres.return_value, lines[1:2], mock_chatter, ['previous1']),
                call(auditor_postgres.return_value, lines[2:3], mock_chatter, ['previous2']),
                call(auditor_postgres.return_value, lines[3:4], mock_chatter, ['previous3']),
                call(auditor_postgres.return_value, lines[4:5], mock_chatter, ['previous4']),
                call(auditor_postgres.return_value, lines[5:6], mock_chatter, ['previous5']),
                call(auditor_postgres.return_value, lines[6:7], mock_chatter, ['previous6']),
            ]
        ),
    ]
    for params, cycles, exp_call_transcript2commands in tests:
        parameters.side_effect = [params]
        load_from_json.return_value.staged_commands_as_instructions.side_effect = [["theCommandAsInstructions"]]
        schema_key2instruction.side_effect = ["theSchemaKey2Instructions"]
        transcript2commands.side_effect = [
            (["previous1"], ["effects1"]),
            (["previous2"], ["effects2"]),
            (["previous3"], ["effects3"]),
            (["previous4"], ["effects4"]),
            (["previous5"], ["effects5"]),
            (["previous6"], ["effects6"]),
            (["previous7"], ["effects7"]),
        ]
        helper.settings.side_effect = [mock_settings]
        mock_settings.llm_text.vendor = "theVendor"
        mock_settings.llm_text_model.side_effect = ["theModel"]
        helper.aws_s3_credentials.side_effect = ["theAwsCredentials"]
        helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
        case_store.return_value.get_case.side_effect = [RecordCase(
            name="theName",
            transcript=lines,
            limited_chart={"limited": "chart"},
            profile="theProfile",
            validation_status=CaseStatus.REVIEW,
            batch_identifier="theBatchIdentifier",
            tags={"tag1": "tag1", "tag2": "tag2"},
            id=147,
        )]
        generated_note_store.return_value.insert.side_effect = [RecordGeneratedNote(case_id=147, id=333)]
        audio_interpreter.side_effect = [mock_chatter]
        mock_chatter.identification = identification

        tested = CaseRunner
        tested.run()

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call({'limited': 'chart'}),
            call().staged_commands_as_instructions("theSchemaKey2Instructions"),
        ]
        assert load_from_json.mock_calls == calls
        calls = [
            call('_NoteUuid'),
        ]
        for idx in range(cycles):
            calls.append(call().set_cycle(idx + 1))
        assert get_discussion.mock_calls == calls
        calls = [call()]
        assert schema_key2instruction.mock_calls == calls
        assert transcript2commands.mock_calls == exp_call_transcript2commands
        calls = [
            call.settings(),
            call.aws_s3_credentials(),
            call.postgres_credentials(),
        ]
        assert helper.mock_calls == calls
        calls = [
            call('thePostgresCredentials'),
            call().get_case('theCase'),
        ]
        assert case_store.mock_calls == calls
        calls = [
            call('thePostgresCredentials'),
            call().insert(GeneratedNote(
                case_id=147,
                cycle_duration=0,
                cycle_count=cycles,
                cycle_transcript_overlap=100,
                text_llm_vendor='theVendor',
                text_llm_name='theModel',
                note_json=[],
                hyperscribe_version='',
                staged_questionnaires={},
                transcript2instructions={},
                instruction2parameters={},
                parameters2command={},
                failed=True,
                errors={},
                id=0,
            )),
        ]
        assert generated_note_store.mock_calls == calls
        calls = [call(mock_settings, 'theAwsCredentials', load_from_json.return_value, identification)]
        assert audio_interpreter.mock_calls == calls
        calls = [
            call('theName', 0, 333),
        ]
        for idx in range(cycles):
            calls.append(call().set_cycle(idx + 1))
        calls.append(call().finalize([]), )
        assert auditor_postgres.mock_calls == calls
        assert mock_chatter.mock_calls == []
        calls = [call.llm_text_model()]
        assert mock_settings.mock_calls == calls
        reset_mocks()
