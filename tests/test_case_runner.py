from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from case_runner import CaseRunner
from evaluations.datastores.datastore_case import DatastoreCase
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
        call().add_argument("--case", type=str, required=True, help="The case to run"),
        call().add_argument("--cycles", type=int, required=True, help="Split the transcript in as many cycles"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("case_runner.AudioInterpreter")
@patch("case_runner.HelperEvaluation")
@patch.object(DatastoreCase, "already_generated")
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
        already_generated,
        helper,
        audio_interpreter,
):
    mock_chatter = MagicMock()
    mock_auditor = MagicMock()
    def reset_mocks():
        parameters.reset_mock()
        load_from_json.reset_mock()
        get_discussion.reset_mock()
        schema_key2instruction.reset_mock()
        transcript2commands.reset_mock()
        already_generated.reset_mock()
        helper.reset_mock()
        audio_interpreter.reset_mock()
        mock_chatter.reset_mock()
        mock_auditor.reset_mock()

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
    already_generated.side_effect = [False]
    parameters.side_effect = [Namespace(case="theCase", cycles=3)]
    load_from_json.return_value.staged_commands_as_instructions.side_effect = []
    schema_key2instruction.side_effect = []
    transcript2commands.side_effect = []
    helper.get_auditor.side_effect = []
    mock_auditor.limited_chart.side_effect = []
    mock_auditor.full_transcript.side_effect = []
    mock_auditor.settings = "theSettings"
    mock_auditor.s3_credentials = "theAwsCredentials"
    audio_interpreter.side_effect = []
    mock_chatter.identification = identification

    tested = CaseRunner
    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call("theCase")]
    assert already_generated.mock_calls == calls
    assert load_from_json.mock_calls == []
    assert get_discussion.mock_calls == []
    assert schema_key2instruction.mock_calls == []
    assert transcript2commands.mock_calls == []
    assert helper.mock_calls == []
    assert audio_interpreter.mock_calls == []
    assert mock_chatter.mock_calls == []
    assert mock_auditor.mock_calls == []
    reset_mocks()

    # case exists
    tests = [
        # less than 1 cycle
        (
            Namespace(case="theCase", cycles=0),
            1,
            [
                call(mock_auditor, lines[0:7], mock_chatter, ['theCommandAsInstructions']),
            ]
        ),
        # some cycles
        (
            Namespace(case="theCase", cycles=3),
            3,
            [
                call(mock_auditor, lines[0:3], mock_chatter, ["theCommandAsInstructions"]),
                call(mock_auditor, lines[3:6], mock_chatter, ['previous1']),
                call(mock_auditor, lines[6:7], mock_chatter, ['previous2']),
            ]
        ),
        (
            Namespace(case="theCase", cycles=4),
            4,
            [
                call(mock_auditor, lines[0:2], mock_chatter, ["theCommandAsInstructions"]),
                call(mock_auditor, lines[2:4], mock_chatter, ['previous1']),
                call(mock_auditor, lines[4:6], mock_chatter, ['previous2']),
                call(mock_auditor, lines[6:7], mock_chatter, ['previous3']),
            ]
        ),
        # cycles more than the transcript turns
        (
            Namespace(case="theCase", cycles=10),
            7,
            [
                call(mock_auditor, lines[0:1], mock_chatter, ["theCommandAsInstructions"]),
                call(mock_auditor, lines[1:2], mock_chatter, ['previous1']),
                call(mock_auditor, lines[2:3], mock_chatter, ['previous2']),
                call(mock_auditor, lines[3:4], mock_chatter, ['previous3']),
                call(mock_auditor, lines[4:5], mock_chatter, ['previous4']),
                call(mock_auditor, lines[5:6], mock_chatter, ['previous5']),
                call(mock_auditor, lines[6:7], mock_chatter, ['previous6']),
            ]
        ),
    ]
    for params, cycles, exp_call_transcript2commands in tests:
        already_generated.side_effect = [True]
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
        helper.get_auditor.side_effect = [mock_auditor]
        mock_auditor.limited_chart.side_effect = [{"limited": "chart"}]
        mock_auditor.full_transcript.side_effect = [{
            "cycle_001": lines[0:2],
            "cycle_002": lines[2:5],
            "cycle_003": lines[5:7],
        }]
        mock_auditor.settings = "theSettings"
        mock_auditor.s3_credentials = "theAwsCredentials"
        audio_interpreter.side_effect = [mock_chatter]
        mock_chatter.identification = identification

        tested = CaseRunner
        tested.run()

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [call("theCase")]
        assert already_generated.mock_calls == calls
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
            call.get_auditor("theCase", 0),
        ]
        assert helper.mock_calls == calls
        calls = [call("theSettings", 'theAwsCredentials', load_from_json.return_value, identification)]
        assert audio_interpreter.mock_calls == calls
        calls = [
            call('theName', 0, 333),
        ]
        for idx in range(cycles):
            calls.append(call().set_cycle(idx + 1))
        assert mock_chatter.mock_calls == []
        calls = [
            call.full_transcript(),
            call.limited_chart(),
        ]
        for idx in range(cycles):
            calls.append(call.set_cycle(idx + 1))
        calls.append(call.case_finalize([]))
        assert mock_auditor.mock_calls == calls
        reset_mocks()
