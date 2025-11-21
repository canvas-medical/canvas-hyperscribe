import re
from http import HTTPStatus
from unittest.mock import patch, call

from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials

from hyperscribe.handlers.customization_display import CustomizationDisplay
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.customization import Customization as UserOptions
from hyperscribe.structures.default_tab import DefaultTab
from tests.helper import MockClass

# Disable automatic route resolution
CustomizationDisplay._ROUTES = {}


def helper_instance():
    # Minimal fake event with method context
    event = MockClass(context={"method": "GET"})
    secrets = {
        "key": "value",
        "APISigningKey": "theAPISigningKey",
    }
    environment = {Constants.CUSTOMER_IDENTIFIER: "customerIdentifier"}
    view = CustomizationDisplay(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    return view


def test_class():
    assert issubclass(CustomizationDisplay, SimpleAPI)


def test_constants():
    # PREFIX exists (even if None)
    assert hasattr(CustomizationDisplay, "PREFIX")


@patch.object(Authenticator, "check")
def test_authenticate(check):
    def reset_mocks():
        check.reset_mock()

    tested = helper_instance()
    tested.request = MockClass(query_params={"ts": "123", "sig": "abc"})
    creds = Credentials(tested.request)
    tests = [
        (True, True),
        (False, False),
    ]
    for check_side_effect, expected in tests:
        check.side_effect = [check_side_effect]
        result = tested.authenticate(creds)
        assert result is expected

        calls = [call("theAPISigningKey", 3600, {"ts": "123", "sig": "abc"})]
        assert check.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.handlers.customization_display.AwsS3Credentials")
@patch("hyperscribe.handlers.customization_display.Customization")
def test_customizations(customization, aws_s3_credentials):
    def reset_mocks():
        customization.reset_mock()
        aws_s3_credentials.reset_mock()

    tested = helper_instance()
    # all good
    tested.request = MockClass(
        headers={
            "canvas-logged-in-user-id": "theUserId",
            "canvas-logged-in-user-type": "Staff",
        },
    )
    customization.customizations.side_effect = [
        UserOptions(
            custom_prompts=[
                CustomPrompt(command="Command1", prompt="Prompt1", active=True),
                CustomPrompt(command="Command2", prompt="Prompt2", active=True),
                CustomPrompt(command="Command3", prompt="Prompt3", active=False),
                CustomPrompt(command="Command4", prompt="", active=True),
            ],
            ui_default_tab=DefaultTab.TRANSCRIPT,
        )
    ]
    aws_s3_credentials.from_dictionary.side_effect = ["theAwsCredentials"]

    result = tested.customizations()
    expected = [
        JSONResponse(
            content={
                "customPrompts": [
                    {"command": "Command1", "prompt": "Prompt1", "active": True},
                    {"command": "Command2", "prompt": "Prompt2", "active": True},
                    {"command": "Command3", "prompt": "Prompt3", "active": False},
                    {"command": "Command4", "prompt": "", "active": True},
                ],
                "uiDefaultTab": "transcript",
            },
            status_code=HTTPStatus(200),
        )
    ]
    assert result == expected

    calls = [call.customizations("theAwsCredentials", "customerIdentifier", "theUserId")]
    assert customization.mock_calls == calls
    calls = [
        call.from_dictionary(
            {
                "key": "value",
                "APISigningKey": "theAPISigningKey",
            }
        )
    ]
    assert aws_s3_credentials.mock_calls == calls
    reset_mocks()

    # invalid user type
    tested.request = MockClass(
        headers={
            "canvas-logged-in-user-id": "theUserId",
            "canvas-logged-in-user-type": "Customer",
        },
    )

    customization.customizations.side_effect = []
    aws_s3_credentials.from_dictionary.side_effect = []

    result = tested.customizations()
    expected = []
    assert result == expected

    assert customization.mock_calls == []
    assert aws_s3_credentials.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.customization_display.AwsS3Credentials")
@patch("hyperscribe.handlers.customization_display.Customization")
def test_command_save(customization, aws_s3_credentials):
    def reset_mocks():
        customization.reset_mock()
        aws_s3_credentials.reset_mock()

    tested = helper_instance()
    # all good
    tested.request = MockClass(
        headers={
            "canvas-logged-in-user-id": "theUserId",
            "canvas-logged-in-user-type": "Staff",
        },
        json=lambda: {"command": "theCommand", "prompt": "thePrompt", "active": True},
    )

    customization.save_custom_prompt.side_effect = [MockClass(content=b"All good", status_code=200)]
    aws_s3_credentials.from_dictionary.side_effect = ["theAwsCredentials"]

    result = tested.command_save()
    expected = [JSONResponse(content={"response": "All good"}, status_code=HTTPStatus(200))]
    assert result == expected

    calls = [
        call.save_custom_prompt(
            "theAwsCredentials",
            "customerIdentifier",
            "theUserId",
            CustomPrompt(command="theCommand", prompt="thePrompt", active=True),
        )
    ]
    assert customization.mock_calls == calls
    calls = [
        call.from_dictionary(
            {
                "key": "value",
                "APISigningKey": "theAPISigningKey",
            }
        )
    ]
    assert aws_s3_credentials.mock_calls == calls
    reset_mocks()

    # invalid user type
    tested.request = MockClass(
        headers={
            "canvas-logged-in-user-id": "theUserId",
            "canvas-logged-in-user-type": "Customer",
        },
        json=lambda: {"command": "theCommand", "prompt": "thePrompt", "active": True},
    )

    customization.save_custom_prompt.side_effect = []
    aws_s3_credentials.from_dictionary.side_effect = []

    result = tested.command_save()
    expected = []
    assert result == expected

    assert customization.mock_calls == []
    assert aws_s3_credentials.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.customization_display.AwsS3Credentials")
@patch("hyperscribe.handlers.customization_display.Customization")
def test_ui_default_tab_save(customization, aws_s3_credentials):
    def reset_mocks():
        customization.reset_mock()
        aws_s3_credentials.reset_mock()

    tested = helper_instance()
    # all good
    tested.request = MockClass(
        headers={
            "canvas-logged-in-user-id": "theUserId",
            "canvas-logged-in-user-type": "Staff",
        },
        json=lambda: {"uiDefaultTab": "feedback"},
    )

    customization.save_ui_default_tab.side_effect = [MockClass(content=b"All good", status_code=200)]
    aws_s3_credentials.from_dictionary.side_effect = ["theAwsCredentials"]

    result = tested.ui_default_tab_save()
    expected = [JSONResponse(content={"response": "All good"}, status_code=HTTPStatus(200))]
    assert result == expected

    calls = [
        call.save_ui_default_tab(
            "theAwsCredentials",
            "customerIdentifier",
            "theUserId",
            DefaultTab.FEEDBACK,
        )
    ]
    assert customization.mock_calls == calls
    calls = [
        call.from_dictionary(
            {
                "key": "value",
                "APISigningKey": "theAPISigningKey",
            }
        )
    ]
    assert aws_s3_credentials.mock_calls == calls
    reset_mocks()

    # invalid user type
    tested.request = MockClass(
        headers={
            "canvas-logged-in-user-id": "theUserId",
            "canvas-logged-in-user-type": "Customer",
        },
        json=lambda: {"command": "theCommand", "prompt": "thePrompt", "active": True},
    )

    customization.save_ui_default_tab.side_effect = []
    aws_s3_credentials.from_dictionary.side_effect = []

    result = tested.ui_default_tab_save()
    expected = []
    assert result == expected

    assert customization.mock_calls == []
    assert aws_s3_credentials.mock_calls == []
    reset_mocks()
