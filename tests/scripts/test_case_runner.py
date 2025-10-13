from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from hyperscribe.libraries.limited_cache_loader import LimitedCacheLoader
from scripts.case_runner import CaseRunner
from evaluations.datastores.datastore_case import DatastoreCase
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


@patch("scripts.case_runner.ArgumentParser")
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
        call().add_argument(
            "--cycles",
            type=int,
            default=0,
            help="Split the transcript in as many cycles, use the stored cycles if not provided.",
        ),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("scripts.case_runner.AudioInterpreter")
@patch("scripts.case_runner.HelperEvaluation")
@patch.object(DatastoreCase, "already_generated")
@patch.object(Commander, "transcript2commands")
@patch.object(ImplementedCommands, "schema_key2instruction")
@patch.object(CachedSdk, "get_discussion")
@patch.object(LimitedCacheLoader, "load_from_json")
@patch.object(CaseRunner, "prepare_cycles")
@patch.object(CaseRunner, "parameters")
def test_run(
    parameters,
    prepare_cycles,
    load_from_json,
    get_discussion,
    schema_key2instruction,
    transcript2commands,
    already_generated,
    helper,
    audio_interpreter,
    capsys,
):
    mock_chatter = MagicMock()
    mock_auditor = MagicMock()

    def reset_mocks():
        parameters.reset_mock()
        prepare_cycles.reset_mock()
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
        patient_uuid="_PatientUuid",
        note_uuid="theNoteUuid",
        provider_uuid="_ProviderUuid",
        canvas_instance="runner-environment",
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
    prepare_cycles.side_effect = []
    load_from_json.return_value.staged_commands_as_instructions.side_effect = []
    schema_key2instruction.side_effect = []
    transcript2commands.side_effect = []
    helper.get_auditor.side_effect = []
    mock_auditor.limited_chart.side_effect = []
    mock_auditor.full_transcript.side_effect = []
    mock_auditor.note_uuid.side_effect = []
    mock_auditor.settings = "theSettings"
    mock_auditor.s3_credentials = "theAwsCredentials"
    audio_interpreter.side_effect = []
    mock_chatter.identification = identification

    tested = CaseRunner
    tested.run()

    assert capsys.readouterr().out == "\n".join(["Case 'theCase' not generated yet", ""])

    calls = [call()]
    assert parameters.mock_calls == calls
    assert prepare_cycles.mock_calls == []
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
    already_generated.side_effect = [True]
    prepare_cycles.side_effect = [{"cycle_001": lines[0:3], "cycle_002": lines[3:5], "cycle_003": lines[5:]}]
    parameters.side_effect = [Namespace(case="theCase", cycles=3)]
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
    mock_auditor.full_transcript.side_effect = ["theFullTranscript"]
    mock_auditor.note_uuid.side_effect = ["theNoteUuid"]
    mock_auditor.settings = "theSettings"
    mock_auditor.s3_credentials = "theAwsCredentials"
    audio_interpreter.side_effect = [mock_chatter]
    mock_chatter.identification = identification

    tested = CaseRunner
    tested.run()

    assert capsys.readouterr().out == "\n".join([])

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call("theFullTranscript", 3)]
    assert prepare_cycles.mock_calls == calls
    calls = [call("theCase")]
    assert already_generated.mock_calls == calls
    calls = [call({"limited": "chart"}), call().staged_commands_as_instructions("theSchemaKey2Instructions")]
    assert load_from_json.mock_calls == calls
    calls = [call("theNoteUuid"), call().set_cycle(1), call().set_cycle(2), call().set_cycle(3)]
    assert get_discussion.mock_calls == calls
    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    calls = [
        call(mock_auditor, lines[0:3], mock_chatter, ["theCommandAsInstructions"]),
        call(mock_auditor, lines[3:5], mock_chatter, ["previous1"]),
        call(mock_auditor, lines[5:], mock_chatter, ["previous2"]),
    ]
    assert transcript2commands.mock_calls == calls
    calls = [call.get_auditor("theCase", 0)]
    assert helper.mock_calls == calls
    calls = [call("theSettings", "theAwsCredentials", load_from_json.return_value, identification)]
    assert audio_interpreter.mock_calls == calls
    assert mock_chatter.mock_calls == []
    calls = [
        call.full_transcript(),
        call.note_uuid(),
        call.limited_chart(),
        call.set_cycle(1),
        call.set_cycle(2),
        call.set_cycle(3),
        call.case_finalize({}),
    ]
    assert mock_auditor.mock_calls == calls
    reset_mocks()

    # errors
    error = RuntimeError("There was an error")
    already_generated.side_effect = [True]
    parameters.side_effect = [Namespace(case="theCase", cycles=3)]
    prepare_cycles.side_effect = [{"cycle_001": lines[0:3], "cycle_002": lines[3:5], "cycle_003": lines[5:]}]
    load_from_json.return_value.staged_commands_as_instructions.side_effect = [["theCommandAsInstructions"]]
    schema_key2instruction.side_effect = ["theSchemaKey2Instructions"]
    transcript2commands.side_effect = [(["previous1"], ["effects1"]), error]
    helper.get_auditor.side_effect = [mock_auditor]
    helper.trace_error.side_effect = [{"error": "test"}]
    mock_auditor.limited_chart.side_effect = [{"limited": "chart"}]
    mock_auditor.full_transcript.side_effect = ["theFullTranscript"]
    mock_auditor.note_uuid.side_effect = ["theNoteUuid"]
    mock_auditor.settings = "theSettings"
    mock_auditor.s3_credentials = "theAwsCredentials"
    audio_interpreter.side_effect = [mock_chatter]
    mock_chatter.identification = identification

    tested = CaseRunner
    tested.run()

    assert capsys.readouterr().out == "\n".join([])

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call("theFullTranscript", 3)]
    assert prepare_cycles.mock_calls == calls
    calls = [call("theCase")]
    assert already_generated.mock_calls == calls
    calls = [call({"limited": "chart"}), call().staged_commands_as_instructions("theSchemaKey2Instructions")]
    assert load_from_json.mock_calls == calls
    calls = [call("theNoteUuid"), call().set_cycle(1), call().set_cycle(2)]
    assert get_discussion.mock_calls == calls
    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    calls = [
        call(mock_auditor, lines[0:3], mock_chatter, ["theCommandAsInstructions"]),
        call(mock_auditor, lines[3:5], mock_chatter, ["previous1"]),
    ]
    assert transcript2commands.mock_calls == calls
    calls = [call.get_auditor("theCase", 0), call.trace_error(error)]
    assert helper.mock_calls == calls
    calls = [call("theSettings", "theAwsCredentials", load_from_json.return_value, identification)]
    assert audio_interpreter.mock_calls == calls
    assert mock_chatter.mock_calls == []
    calls = [
        call.full_transcript(),
        call.note_uuid(),
        call.limited_chart(),
        call.set_cycle(1),
        call.set_cycle(2),
        call.case_finalize({"error": "test"}),
    ]
    assert mock_auditor.mock_calls == calls
    reset_mocks()


def test_prepare_cycles():
    tested = CaseRunner
    lines = [
        Line(speaker="theSpeaker1", text="theText1"),
        Line(speaker="theSpeaker2", text="theText2"),
        Line(speaker="theSpeaker3", text="theText3"),
        Line(speaker="theSpeaker4", text="theText4"),
        Line(speaker="theSpeaker5", text="theText5"),
        Line(speaker="theSpeaker6", text="theText6"),
        Line(speaker="theSpeaker7", text="theText7"),
    ]
    full_transcript = {"cycle_001": lines[0:3], "cycle_002": lines[3:]}
    tests = [
        (0, {"cycle_001": lines[0:3], "cycle_002": lines[3:]}),
        (1, {"cycle_001": lines[0:]}),
        (2, {"cycle_001": lines[0:4], "cycle_002": lines[4:]}),
        (3, {"cycle_001": lines[0:3], "cycle_002": lines[3:5], "cycle_003": lines[5:]}),
        (4, {"cycle_001": lines[0:2], "cycle_002": lines[2:4], "cycle_003": lines[4:6], "cycle_004": lines[6:]}),
        (
            5,
            {
                "cycle_001": lines[0:2],
                "cycle_002": lines[2:4],
                "cycle_003": lines[4:5],
                "cycle_004": lines[5:6],
                "cycle_005": lines[6:],
            },
        ),
        (
            6,
            {
                "cycle_001": lines[0:2],
                "cycle_002": lines[2:3],
                "cycle_003": lines[3:4],
                "cycle_004": lines[4:5],
                "cycle_005": lines[5:6],
                "cycle_006": lines[6:],
            },
        ),
        (
            7,
            {
                "cycle_001": lines[0:1],
                "cycle_002": lines[1:2],
                "cycle_003": lines[2:3],
                "cycle_004": lines[3:4],
                "cycle_005": lines[4:5],
                "cycle_006": lines[5:6],
                "cycle_007": lines[6:],
            },
        ),
        (
            8,
            {
                "cycle_001": lines[0:1],
                "cycle_002": lines[1:2],
                "cycle_003": lines[2:3],
                "cycle_004": lines[3:4],
                "cycle_005": lines[4:5],
                "cycle_006": lines[5:6],
                "cycle_007": lines[6:],
            },
        ),
    ]
    for cycles, exp_result in tests:
        result = tested.prepare_cycles(full_transcript, cycles)
        assert result == exp_result
