import pytest

from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.memory_log import MemoryLog
from integrations.helper_settings import HelperSettings


def pytest_addoption(parser):
    parser.addoption(
        "--integration-difference-levels",
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


def pytest_configure(config):
    settings = HelperSettings().settings()
    parameters = {
        "integration-difference-levels": config.getoption("--integration-difference-levels", default=""),
        "patient-uuid": config.getoption("--patient-uuid", default=""),
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


@pytest.fixture
def allowed_levels(request):
    return [
        level.strip()
        for level in request.config.getoption("--integration-difference-levels").split(",")
    ]


@pytest.fixture
def audio_interpreter(request):
    settings = HelperSettings.settings()
    patient_uuid = request.config.getoption("--patient-uuid")
    cache = LimitedCache(patient_uuid, {})
    note_uuid = HelperSettings.get_note_uuid(patient_uuid) if patient_uuid else "noteUuid"
    provider_uuid = HelperSettings.get_provider_uuid(patient_uuid) if patient_uuid else "providerUuid"
    return AudioInterpreter(settings, cache, patient_uuid, note_uuid, provider_uuid)
