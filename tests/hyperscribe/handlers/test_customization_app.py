from unittest.mock import patch, call

from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.application import Application

from hyperscribe.handlers.customization_app import CustomizationApp
from hyperscribe.libraries.constants import Constants


def helper_instance():
    event = Event(EventRequest())
    secrets = {
        "key": "value",
        "APISigningKey": "theAPISigningKey",
    }
    environment = {Constants.CUSTOMER_IDENTIFIER: "customerIdentifier"}
    return CustomizationApp(event, secrets, environment)
    # view._path_pattern = re.compile(r".*")
    # return view


def test_class():
    assert issubclass(CustomizationApp, Application)


@patch("hyperscribe.handlers.customization_app.render_to_string")
@patch("hyperscribe.handlers.customization_app.LaunchModalEffect")
@patch("hyperscribe.handlers.customization_app.Authenticator")
def test_on_open(authenticator, launch_modal_effect, render_to_string):
    def reset_mocks():
        authenticator.reset_mock()
        launch_modal_effect.reset_mock()
        render_to_string.reset_mock()

    tested = helper_instance()

    authenticator.presigned_url_no_params.side_effect = ["url1", "url2"]
    launch_modal_effect.return_value.apply.side_effect = ["theLaunchModalEffect"]
    launch_modal_effect.TargetType.RIGHT_CHART_PANE = "RIGHT_CHART_PANE"
    render_to_string.side_effect = ["theRenderedString"]

    result = tested.on_open()
    expected = "theLaunchModalEffect"
    assert result == expected

    calls = [
        call.presigned_url_no_params("theAPISigningKey", "/plugin-io/api/hyperscribe/customization/commands"),
        call.presigned_url_no_params("theAPISigningKey", "/plugin-io/api/hyperscribe/customization/command"),
    ]
    assert authenticator.mock_calls == calls
    calls = [call(content="theRenderedString", target="RIGHT_CHART_PANE"), call().apply()]
    assert launch_modal_effect.mock_calls == calls
    calls = [call("templates/customization.html", {"listCommands": "url1", "saveCommandPromptURL": "url2"})]
    assert render_to_string.mock_calls == calls
    reset_mocks()
