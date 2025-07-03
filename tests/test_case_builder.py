from unittest.mock import patch, call
import sys
from case_builder import CaseBuilder
from evaluations.case_builders.builder_audit_url import BuilderAuditUrl
from evaluations.case_builders.builder_delete import BuilderDelete
from evaluations.case_builders.builder_direct_from_tuning_full import BuilderDirectFromTuningFull
from evaluations.case_builders.builder_direct_from_tuning_split import BuilderDirectFromTuningSplit
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning
from evaluations.case_builders.builder_summarize import BuilderSummarize
from evaluations.case_builders.builder_from_chart_transcript import BuilderFromChartTranscript

@patch.object(BuilderDirectFromTuningFull, "run")
@patch.object(BuilderDirectFromTuningSplit, "run")
@patch.object(BuilderFromChartTranscript, "run")
@patch.object(BuilderSummarize, "run")
@patch.object(BuilderAuditUrl, "run")
@patch.object(BuilderFromTuning, "run")
@patch.object(BuilderFromTranscript, "run")
@patch.object(BuilderFromMp3, "run")
@patch.object(BuilderDelete, "run")

@patch.object(BuilderDirectFromTuningFull, "run")
@patch.object(BuilderDirectFromTuningSplit, "run")
@patch.object(BuilderFromChartTranscript, "run")
@patch.object(BuilderSummarize, "run")
@patch.object(BuilderAuditUrl, "run")
@patch.object(BuilderFromTuning, "run")
@patch.object(BuilderFromTranscript, "run")
@patch.object(BuilderFromMp3, "run")
@patch.object(BuilderDelete, "run")
def test_run(
    run_delete,
    run_mp3,
    run_transcript,
    run_tuning,
    run_audit,
    run_summarize,
    run_chart_transcript,
    run_direct_split,
    run_direct_full,
    capsys,
):
    def reset_mocks():
        run_delete.reset_mock()
        run_mp3.reset_mock()
        run_transcript.reset_mock()
        run_tuning.reset_mock()
        run_audit.reset_mock()
        run_summarize.reset_mock()
        run_chart_transcript.reset_mock()
        run_direct_split.reset_mock()
        run_direct_full.reset_mock()

    tests = [
        (['--delete'], "", [call()], [], [], [], [], [], [], []),
        (['--mp3'], "", [], [call()], [], [], [], [], [], []),
        (['--transcript'], "", [], [], [call()], [], [], [], [], []),
        (['--tuning-json'], "", [], [], [], [call()], [], [], [], []),
        (['--audit'], "", [], [], [], [], [call()], [], [], []),
        (['--summarize'], "", [], [], [], [], [], [call()], [], []),
        (['--direct-split'], "", [], [], [], [], [], [], [call()], []),
        (['--direct-full'], "", [], [], [], [], [], [], [], [call()]),
        (['--chart-transcript'], "", [], [], [], [], [], [call()], [], []),
        ([], "no explicit action to perform\n", [], [], [], [], [], [], [], []),
    ]

    for (arguments, exp_out, call_delete, call_mp3, call_transcript, call_tuning,
        call_audit, call_summarize, call_chart_transcript, call_direct_split, call_direct_full) in tests:
        tested = CaseBuilder()
        tested.run(arguments)

        assert capsys.readouterr().out == exp_out
        assert run_delete.mock_calls == call_delete
        assert run_mp3.mock_calls == call_mp3
        assert run_transcript.mock_calls == call_transcript
        assert run_tuning.mock_calls == call_tuning
        assert run_audit.mock_calls == call_audit
        assert run_summarize.mock_calls == call_summarize
        assert run_chart_transcript.mock_calls == call_chart_transcript
        assert run_direct_split.mock_calls == call_direct_split
        assert run_direct_full.mock_calls == call_direct_full
        reset_mocks()