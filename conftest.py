import json
import uuid
from re import search
from subprocess import check_output

import pytest

from evaluations.constants import Constants
from evaluations.datastores.sqllite.store_cases import StoreCases
from evaluations.datastores.store_results import StoreResults
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_result import EvaluationResult
from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.constants import Constants as HyperscribeConstants
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    test_file = report.location[0]

    # limiting the collect to the "evaluation/" tests
    if report.when == "call" and test_file.startswith("evaluations/"):
        test_name = report.location[2]
        test_case = "n/a"
        pattern = r"test_(.+)\[(.+)\]"
        if match := search(pattern, report.location[2]):
            test_name = match.group(1)
            test_case = match.group(2)

        errors = ""
        if report.failed and call.excinfo is not None:
            errors = str(call.excinfo.value)

        plugin_commit = check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()

        StoreResults.insert(
            EvaluationResult(
                run_uuid=item.config.unique_session_id,
                commit_uuid=plugin_commit,
                milliseconds=report.duration * 1000,
                passed=report.passed,
                test_file=test_file,
                test_name=test_name,
                test_case=test_case,
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
    parser.addoption(
        Constants.OPTION_PATIENT_UUID,
        action="store",
        default="",
        help="patient uuid to consider",
    )
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


def pytest_configure(config):
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


def pytest_unconfigure(config):
    if config.getoption(Constants.OPTION_PRINT_LOGS, default=False):
        note_uuid_list = list(MemoryLog.ENTRIES.keys())
        for note_uuid in note_uuid_list:
            print(MemoryLog.end_session(note_uuid))


@pytest.fixture
def allowed_levels(request):
    return [
        level.strip()
        for level in request.config.getoption(Constants.OPTION_DIFFERENCE_LEVELS).split(",")
    ]


@pytest.fixture
def audio_interpreter(request):
    settings = HelperEvaluation.settings()
    aws_s3 = AwsS3Credentials.from_dictionary({})
    if request.config.getoption(Constants.OPTION_STORE_LOGS, default=False):
        aws_s3 = HelperEvaluation.aws_s3_credentials()

    patient_uuid = HyperscribeConstants.FAUX_PATIENT_UUID
    note_uuid = HyperscribeConstants.FAUX_NOTE_UUID
    provider_uuid = HyperscribeConstants.FAUX_PROVIDER_UUID
    cache = LimitedCache(patient_uuid, {})

    if forced_patient_uuid := request.config.getoption(Constants.OPTION_PATIENT_UUID):
        patient_uuid = forced_patient_uuid
        cache.patient_uuid = forced_patient_uuid

    if patient_uuid and patient_uuid != HyperscribeConstants.FAUX_PATIENT_UUID:
        note_uuid = HelperEvaluation.get_note_uuid(patient_uuid)
        provider_uuid = HelperEvaluation.get_provider_uuid(patient_uuid)
    elif case := StoreCases.get(request.node.callspec.id):
        # ^ if there is no provided patient uuid and this is a built case
        cache = LimitedCache.load_from_json(json.loads(case.limited_cache))

    return AudioInterpreter(settings, aws_s3, cache, patient_uuid, note_uuid, provider_uuid)
