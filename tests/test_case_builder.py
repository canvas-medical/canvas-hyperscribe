from unittest.mock import patch, call

from case_builder import CaseBuilder
from evaluations.case_builders.builder_delete import BuilderDelete
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning


@patch.object(BuilderFromTuning, "run")
@patch.object(BuilderFromTranscript, "run")
@patch.object(BuilderFromMp3, "run")
@patch.object(BuilderDelete, "run")
def test_run(
        run_delete,
        run_mp3,
        run_transcript,
        run_tuning,
):
    def reset_mocks():
        run_delete.reset_mock()
        run_mp3.reset_mock()
        run_transcript.reset_mock()
        run_tuning.reset_mock()

    tests = [
        (['--delete'], [call()], [], [], []),
        (['--transcript'], [], [call()], [], []),
        (['--tuning-json'], [], [], [call()], []),
        ([], [], [], [], [call()]),
    ]
    tested = CaseBuilder
    for arguments, call_delete, call_transcript, call_tuning, call_mp3 in tests:
        tested.run(arguments)
        assert run_delete.mock_calls == call_delete
        assert run_mp3.mock_calls == call_mp3
        assert run_transcript.mock_calls == call_transcript
        assert run_tuning.mock_calls == call_tuning
        reset_mocks()
