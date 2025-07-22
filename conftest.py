# mypy: allow-untyped-defs
import json
import uuid
from pathlib import Path
from re import match
from subprocess import check_output

import pytest

from evaluations.constants import Constants
from evaluations.datastores.filesystem.case import Case as FileSystemCase
from evaluations.datastores.store_results import StoreResults
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_result import EvaluationResult
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.constants import Constants as HyperscribeConstants
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog, ENTRIES
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    test_file = report.location[0]

    # limiting the collect to the "evaluation/" tests
    if report.when == "call" and test_file.startswith("evaluations/test_end2end.py"):
        test_name = report.location[2]
        case_name = "n/a"
        cycle = -1
        pattern_end2end = rf"test_(.+?)\[([^\]]+?)\]"
        pattern_details = rf"test_detail_(.+?)\[(.+)_{Constants.CASE_CYCLE_SUFFIX}_(\d+)\]"
        if result := match(pattern_details, report.location[2]):
            test_name = result.group(1)
            case_name = result.group(2)
            cycle = int(result.group(3))
        elif result := match(pattern_end2end, report.location[2]):
            test_name = result.group(1)
            case_name = result.group(2)
            cycle = -1

        errors = ""
        if report.failed and call.excinfo is not None:
            errors = "\n".join(
                [str(call.excinfo.value), "---"]
                + [value for name, value in item.user_properties if name == "llmExplanation"],
            )

        plugin_commit = check_output(["git", "rev-parse", "--short", "HEAD"]).decode("ascii").strip()

        StoreResults.insert(
            EvaluationResult(
                run_uuid=item.config.unique_session_id,
                commit_uuid=plugin_commit,
                milliseconds=report.duration * 1000,
                passed=report.passed,
                test_file=test_file,
                test_name=test_name,
                case_name=case_name,
                cycle=cycle,
                errors=errors,
            ),
        )

    return report


def pytest_addoption(parser):
    parser.addoption(
        Constants.OPTION_DIFFERENCE_LEVELS,
        action="store",
        default=",".join([Constants.DIFFERENCE_LEVEL_MINOR, Constants.DIFFERENCE_LEVEL_MODERATE]),
        help="Coma seperated list of the levels of meaning difference that are accepted",
    )
    parser.addoption(Constants.OPTION_PATIENT_UUID, action="store", default="", help="patient uuid to consider")
    parser.addoption(
        Constants.OPTION_PRINT_LOGS,
        action="store_true",
        default=False,
        help="Print the logs at the end of the test",
    )
    parser.addoption(
        Constants.OPTION_STORE_LOGS,
        action="store_true",
        default=False,
        help="Store the logs in the configured AWS S3 bucket",
    )
    parser.addoption(Constants.OPTION_END2END, action="store_true", default=False, help="Run the end2end tests")


def pytest_collection_modifyitems(session, config, items):
    list_evaluation_tests = {
        "test_audio2transcript.py",
        "test_end2end.py",
        "test_instruction2parameters.py",
        "test_parameters2command.py",
        "test_staged_questionnaires.py",
        "test_transcript2instructions.py",
    }
    test_files = {
        filename for item in items if (filename := Path(item.location[0]).name) and filename in list_evaluation_tests
    }
    if test_files:
        config.unique_session_id = str(uuid.uuid4())
        settings = HelperEvaluation().settings()
        parameters = {
            "evaluation-difference-levels": config.getoption(Constants.OPTION_DIFFERENCE_LEVELS),
            "patient-uuid": config.getoption(Constants.OPTION_PATIENT_UUID) or "defined at the case level",
            "llm-audio": settings.llm_audio.vendor,
            "llm-text": settings.llm_text.vendor,
            "structured-RfV": settings.structured_rfv,
        }
        for key, value in parameters.items():
            print(f"{key}: {value}")
        #
        end2end = config.getoption(Constants.OPTION_END2END)
        deselected = [
            item
            for item in items
            if (item.name.startswith("test_end2end") and not end2end)
            or (not item.name.startswith("test_end2end") and end2end)
        ]
        if deselected:
            config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if item.name.startswith("test_end2end") is end2end]


def pytest_unconfigure(config):
    if config.getoption(Constants.OPTION_PRINT_LOGS, default=False):
        note_uuid_list = list(ENTRIES.keys())
        for note_uuid in note_uuid_list:
            print(MemoryLog.end_session(note_uuid))


@pytest.fixture
def allowed_levels(request):
    return [level.strip() for level in request.config.getoption(Constants.OPTION_DIFFERENCE_LEVELS).split(",")]


@pytest.fixture
def audio_interpreter(request):
    settings = HelperEvaluation.settings()
    aws_s3 = AwsS3Credentials.from_dictionary({})
    if request.config.getoption(Constants.OPTION_STORE_LOGS, default=False):
        aws_s3 = HelperEvaluation.aws_s3_credentials()

    patient_uuid = HyperscribeConstants.FAUX_PATIENT_UUID
    note_uuid = HyperscribeConstants.FAUX_NOTE_UUID
    provider_uuid = HyperscribeConstants.FAUX_PROVIDER_UUID
    cache = LimitedCache(patient_uuid, provider_uuid, {})

    if forced_patient_uuid := request.config.getoption(Constants.OPTION_PATIENT_UUID):
        patient_uuid = forced_patient_uuid
        cache.patient_uuid = forced_patient_uuid

    if patient_uuid and patient_uuid != HyperscribeConstants.FAUX_PATIENT_UUID:
        note_uuid = HelperEvaluation.get_note_uuid(patient_uuid)
        provider_uuid = HelperEvaluation.get_provider_uuid(patient_uuid)
    elif case := FileSystemCase.get(request.node.callspec.id):
        # ^ if there is no provided patient uuid and this is a built case
        cache = LimitedCache.load_from_json(case.limited_cache)

    identification = IdentificationParameters(
        patient_uuid=patient_uuid,
        note_uuid=note_uuid,
        provider_uuid=provider_uuid,
        canvas_instance=HelperEvaluation.get_canvas_instance(),
    )
    return AudioInterpreter(settings, aws_s3, cache, identification)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    step = "end2end_folder"
    if step in metafunc.fixturenames:
        cases_dir = Path(__file__).parent / "evaluations/cases"
        folders: list[Path] = []

        for case_folder in cases_dir.glob("*"):
            if case_folder.is_dir() is False:
                continue
            folders.append(case_folder)

        metafunc.parametrize(step, folders, ids=lambda path: path.stem)

    step = "audio2transcript_files"
    if step in metafunc.fixturenames:
        parameters: list[tuple[str, str, list[Path], Path]] = []
        if metafunc.function.__name__.startswith("test_detail_"):
            folder = Path(__file__).parent / "evaluations/cases"
        else:
            folder = Path(__file__).parent / "evaluations/situational/audio2transcript/"

        for case in folder.glob("*"):
            if case.is_dir() is False:
                continue
            audios = case / "audios"
            json_file = case / "audio2transcript.json"

            if audios.exists() is False:
                continue

            assert json_file.exists(), f"{case.stem}: no corresponding JSON file found"

            cycle_len = len(f"{Constants.CASE_CYCLE_SUFFIX}_???")
            cycles = json.load(json_file.open("r")).keys()
            cycled_mp3_files: dict[str, list[Path]] = {cycle: [] for cycle in cycles}
            for file in audios.glob(f"{Constants.CASE_CYCLE_SUFFIX}_???_??.mp3"):
                key = file.stem[:cycle_len]
                cycled_mp3_files[key].append(file)

            for cycle, mp3_files in cycled_mp3_files.items():
                parameters.append((case.stem, cycle, sorted(mp3_files, key=lambda x: x.stem), json_file))

        metafunc.parametrize(step, parameters, ids=lambda path: f"{path[0]}_{path[1]}")

    steps = ["transcript2instructions", "instruction2parameters", "parameters2command", "staged_questionnaires"]
    for step in steps:
        if step in metafunc.fixturenames:
            json_files: list[tuple[str, Path]] = []
            if metafunc.function.__name__.startswith("test_detail_"):
                folder = Path(__file__).parent / "evaluations/cases"
                for case in folder.glob("*"):
                    if case.is_dir() is False:
                        continue
                    json_file = case / f"{step}.json"
                    if json_file.exists() is False:
                        continue
                    json_files.append((case.stem, json_file))
            else:
                folder = Path(__file__).parent / f"evaluations/situational/{step}/"
                for json_file in folder.glob("*.json"):
                    json_files.append((json_file.stem, json_file))
            files = [
                (case_name, cycle, json_file)
                for case_name, json_file in json_files
                for cycle in json.load(json_file.open("r")).keys()
                if cycle.startswith(Constants.CASE_CYCLE_SUFFIX)
            ]
            metafunc.parametrize(step, files, ids=lambda path: f"{path[0]}_{path[1]}")
