# mypy: allow-untyped-defs
from pathlib import Path

import pytest

from evaluations.test_audio2transcript import runner_audio2transcript
from evaluations.test_instruction2parameters import runner_instruction2parameters
from evaluations.test_parameters2command import runner_parameters2command
from evaluations.test_staged_questionnaires import runner_staged_questionnaires
from evaluations.test_transcript2instructions import runner_transcript2instructions
from hyperscribe.libraries.audio_interpreter import AudioInterpreter


def force_print(message: str, capsys: pytest.CaptureFixture[str]) -> None:
    with capsys.disabled():
        print(message, end="", flush=True)


def test_detail_audio2transcript(
        audio2transcript_files: tuple[str, str, list[Path], Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_audio2transcript(
        audio2transcript_files,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def test_detail_transcript2instructions(
        transcript2instructions: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_transcript2instructions(
        transcript2instructions,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def test_detail_instruction2parameters(
        instruction2parameters: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_instruction2parameters(
        instruction2parameters,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def test_detail_parameters2command(
        parameters2command: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_parameters2command(
        parameters2command,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def test_detail_staged_questionnaires(
        staged_questionnaires: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_staged_questionnaires(
        staged_questionnaires,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def test_end2end(
        end2end_folder: Path,
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    # TODO refactor to use the AuditorStore rather than the AuditorFile
    # auditor = AuditorFile.default_instance(end2end_folder.stem, 0)
    # failures = []
    #
    # cycles = json.load(auditor.case_file(auditor.TRANSCRIPT2INSTRUCTIONS_FILE).open("r")).keys()
    # # audio2transcript
    # json_file = auditor.case_file(auditor.AUDIO2TRANSCRIPT_FILE)
    # if json_file.exists():
    #     cycle_len = len(f"{Constants.CASE_CYCLE_SUFFIX}_???")
    #     cycled_mp3_files: dict[str, list[Path]] = {cycle: [] for cycle in cycles}
    #     for file in auditor.audio_case_files():
    #         key = file.stem[:cycle_len]
    #         cycled_mp3_files[key].append(file)
    #
    #     force_print("*", capsys)
    #     for cycle, mp3_files in cycled_mp3_files.items():
    #         force_print(".", capsys)
    #         try:
    #             runner_audio2transcript(
    #                 (
    #                     end2end_folder.stem,
    #                     cycle,
    #                     sorted(mp3_files, key=lambda x: x.stem),
    #                     json_file,
    #                 ),
    #                 allowed_levels,
    #                 audio_interpreter,
    #                 capsys,
    #                 request,
    #             )
    #         except AssertionError as e:
    #             failures.append(str(e))
    #
    # # transcript2instructions
    # json_file = auditor.case_file(auditor.TRANSCRIPT2INSTRUCTIONS_FILE)
    # if json_file.exists():
    #     force_print("*", capsys)
    #     for cycle in cycles:
    #         force_print(".", capsys)
    #         try:
    #             runner_transcript2instructions(
    #                 (
    #                     end2end_folder.stem,
    #                     cycle,
    #                     auditor.case_file(auditor.TRANSCRIPT2INSTRUCTIONS_FILE),
    #                 ),
    #                 allowed_levels,
    #                 audio_interpreter,
    #                 capsys,
    #                 request,
    #             )
    #         except AssertionError as e:
    #             failures.append(str(e))
    #
    # # instruction2parameters
    # json_file = auditor.case_file(auditor.INSTRUCTION2PARAMETERS_FILE)
    # if json_file.exists():
    #     force_print("*", capsys)
    #     for cycle in cycles:
    #         force_print(".", capsys)
    #         try:
    #             runner_instruction2parameters(
    #                 (
    #                     end2end_folder.stem,
    #                     cycle,
    #                     auditor.case_file(auditor.INSTRUCTION2PARAMETERS_FILE),
    #                 ),
    #                 allowed_levels,
    #                 audio_interpreter,
    #                 capsys,
    #                 request,
    #             )
    #         except AssertionError as e:
    #             failures.append(str(e))
    #
    # # parameters2command
    # json_file = auditor.case_file(auditor.PARAMETERS2COMMAND_FILE)
    # if json_file.exists():
    #     force_print("*", capsys)
    #     for cycle in cycles:
    #         force_print(".", capsys)
    #         try:
    #             runner_parameters2command(
    #                 (
    #                     end2end_folder.stem,
    #                     cycle,
    #                     auditor.case_file(auditor.PARAMETERS2COMMAND_FILE),
    #                 ),
    #                 allowed_levels,
    #                 audio_interpreter,
    #                 capsys,
    #                 request,
    #             )
    #         except AssertionError as e:
    #             failures.append(str(e))
    #
    # # staged_questionnaires
    # json_file = auditor.case_file(auditor.STAGED_QUESTIONNAIRES_FILE)
    # if json_file.exists():
    #     force_print("*", capsys)
    #     for cycle in cycles:
    #         force_print(".", capsys)
    #         try:
    #             runner_staged_questionnaires(
    #                 (
    #                     end2end_folder.stem,
    #                     cycle,
    #                     auditor.case_file(auditor.STAGED_QUESTIONNAIRES_FILE),
    #                 ),
    #                 allowed_levels,
    #                 audio_interpreter,
    #                 capsys,
    #                 request,
    #             )
    #         except AssertionError as e:
    #             failures.append(str(e))
    #
    # if failures:
    #     pytest.fail("Failures:\n" + "\n".join(failures))
    pass
