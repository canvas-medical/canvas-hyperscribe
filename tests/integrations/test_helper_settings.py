from integrations.helper_settings import HelperSettings
from tests.helper import is_constant


def test_helper_settings():
    tested = HelperSettings
    constants = {
        "DIFFERENCE_LEVELS": ["minor", "moderate", "severe", "critical"],
    }
    assert is_constant(tested, constants)
