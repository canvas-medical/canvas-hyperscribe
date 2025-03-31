import uuid
from re import search
from subprocess import check_output

import pytest

from evaluations.datastores.sqllite.store_cases import StoreCases
from evaluations.datastores.store_results import StoreResults
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_result import EvaluationResult
from hyperscribe.handlers.audio_interpreter import AudioInterpreter
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
        "--evaluation-difference-levels",
        action="store",
        default="minor,moderate",
        help="Coma seperated list of the levels of meaning difference that are accepted",
    )
    parser.addoption(
        "--patient-uuid",
        action="store",
        default="",
        help="patient uuid to consider",
    )
    parser.addoption(
        "--print-logs",
        action="store_true",
        default=False,
        help="Print the logs at the end of the test",
    )
    parser.addoption(
        "--store-logs",
        action="store_true",
        default=False,
        help="Store the logs in the configured AWS S3 bucket",
    )


def pytest_configure(config):
    config.unique_session_id = str(uuid.uuid4())

    settings = HelperEvaluation().settings()
    parameters = {
        "evaluation-difference-levels": config.getoption("--evaluation-difference-levels", default=""),
        "patient-uuid": get_patient_uuid(config),
        "llm-audio": settings.llm_audio.vendor,
        "llm-text": settings.llm_text.vendor,
        "structured-RfV": settings.structured_rfv,
    }
    for key, value in parameters.items():
        print(f"{key}: {value}")


def pytest_unconfigure(config):
    if config.getoption("--print-logs", default=False):
        note_uuid_list = list(MemoryLog.ENTRIES.keys())
        for note_uuid in note_uuid_list:
            print(MemoryLog.end_session(note_uuid))


def get_patient_uuid(config) -> str:
    if result := config.getoption("--patient-uuid"):
        return result
    result = ""
    if (case_name := config.getoption("-k")) and (case := StoreCases.get(case_name)):
        result = case.patient_uuid
    return result


@pytest.fixture
def allowed_levels(request):
    return [
        level.strip()
        for level in request.config.getoption("--evaluation-difference-levels").split(",")
    ]


@pytest.fixture
def audio_interpreter(request):
    settings = HelperEvaluation.settings()
    aws_s3 = AwsS3Credentials(aws_secret="", aws_key="", region="", bucket="")
    if request.config.getoption("--store-logs", default=False):
        aws_s3 = HelperEvaluation.aws_s3_credentials()
    patient_uuid = get_patient_uuid(request.config)
    cache = LimitedCache(patient_uuid, {})
    note_uuid = HelperEvaluation.get_note_uuid(patient_uuid) if patient_uuid else "noteUuid"
    provider_uuid = HelperEvaluation.get_provider_uuid(patient_uuid) if patient_uuid else "providerUuid"
    return AudioInterpreter(settings, aws_s3, cache, patient_uuid, note_uuid, provider_uuid)
