from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from case_runner import CaseRunner
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters


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
        call().add_argument("--result_folder", type=str, required=True, help="Folder to store result files"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("case_runner.uuid4")
@patch("case_runner.rmtree")
@patch("case_runner.Path")
@patch("case_runner.AuditorFile")
@patch("case_runner.AudioInterpreter")
@patch("case_runner.StoreCases")
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
        store_cases,
        audio_interpreter,
        auditor_file,
        path,
        rmtree,
        uuid4,
):
    auditor = MagicMock()
    folder = MagicMock()

    def reset_mocks():
        parameters.reset_mock()
        load_from_json.reset_mock()
        get_discussion.reset_mock()
        schema_key2instruction.reset_mock()
        transcript2commands.reset_mock()
        helper.reset_mock()
        store_cases.reset_mock()
        audio_interpreter.reset_mock()
        auditor_file.reset_mock()
        path.reset_mock()
        rmtree.reset_mock()
        uuid4.reset_mock()
        auditor.reset_mock()
        folder.reset_mock()

    identification = IdentificationParameters(
        patient_uuid='_PatientUuid',
        note_uuid='_NoteUuid',
        provider_uuid='_ProviderUuid',
        canvas_instance='theEnvironment',
    )
    for exists in [True, False]:
        parameters.side_effect = [Namespace(case="theCase", result_folder="theResultFolder")]
        load_from_json.return_value.staged_commands_as_instructions.side_effect = [["theCommandAsInstructions"]]
        schema_key2instruction.side_effect = ["theSchemaKey2Instructions"]
        transcript2commands.side_effect = [
            (["previous1"], ["effects1"]),
            (["previous2"], ["effects2"]),
            (["previous3"], ["effects3"]),
            (["previous4"], ["effects4"]),
        ]
        helper.settings.side_effect = ["theSettings"]
        helper.aws_s3_credentials.side_effect = ["theAwsCredentials"]
        store_cases.get.side_effect = [EvaluationCase(
            environment="theEnvironment",
            limited_cache={"limited": "cache"},
            cycles=3,
        )]
        audio_interpreter.side_effect = ["theChatter"]
        auditor_file.return_value = auditor
        auditor_file.default_instance.return_value = auditor
        auditor.transcript.side_effect = [
            "transcript1",
            "transcript2",
            "transcript3",
        ]
        path.return_value.__truediv__.side_effect = [folder]
        folder.exists.side_effect = [exists]
        uuid4.side_effect = ["theUuid"]

        tested = CaseRunner
        tested.run()

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call({'limited': 'cache'}),
            call().staged_commands_as_instructions("theSchemaKey2Instructions"),
        ]
        assert load_from_json.mock_calls == calls
        calls = [
            call('_NoteUuid'),
            call().set_cycle(1),
            call().set_cycle(2),
            call().set_cycle(3),
        ]
        assert get_discussion.mock_calls == calls
        calls = [call()]
        assert schema_key2instruction.mock_calls == calls
        calls = [
            call(auditor, "transcript1", "theChatter", ["theCommandAsInstructions"]),
            call(auditor, "transcript2", "theChatter", ['previous1']),
            call(auditor, "transcript3", "theChatter", ['previous2']),
        ]
        assert transcript2commands.mock_calls == calls
        calls = [
            call.settings(),
            call.aws_s3_credentials(),
        ]
        assert helper.mock_calls == calls
        calls = [call.get('theCase')]
        assert store_cases.mock_calls == calls
        calls = [call('theSettings', 'theAwsCredentials', load_from_json.return_value, identification)]
        assert audio_interpreter.mock_calls == calls
        calls = [
            call('theCase_run_theUuid', 0, folder),
            call.default_instance('theCase', 0),
            call().transcript(),
            call('theCase_run_theUuid', 1, folder),
            call.default_instance('theCase', 1),
            call().transcript(),
            call('theCase_run_theUuid', 2, folder),
            call.default_instance('theCase', 2),
            call().transcript(),
            call('theCase_run_theUuid', 0, folder),
            call().generate_commands_summary(),
            call().generate_html_summary(),
        ]
        assert auditor_file.mock_calls == calls
        calls = [
            call('theResultFolder'),
            call().__truediv__('theCase_run_theUuid'),
        ]
        assert path.mock_calls == calls
        calls = [call(folder)]
        assert rmtree.mock_calls == calls
        calls = [
            call.transcript(),
            call.transcript(),
            call.transcript(),
            call.generate_commands_summary(),
            call.generate_html_summary(),
        ]
        assert auditor.mock_calls == calls
        calls = [
            call.exists(),
        ]
        if exists is False:
            calls.append(call.mkdir(parents=True))
        assert folder.mock_calls == calls
        calls = [call()]
        assert uuid4.mock_calls == calls
        reset_mocks()
