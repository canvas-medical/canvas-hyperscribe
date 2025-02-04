import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration-difference-levels",
        action="store",
        default="minor,moderate",
        help="Coma seperated list of the levels of meaning difference that are accepted",
    )


@pytest.fixture
def allowed_levels(request):
    return [
        level.strip()
        for level in request.config.getoption("--integration-difference-levels").split(",")
    ]
