from http import HTTPStatus
from unittest.mock import patch, call

from canvas_sdk.effects.simple_api import Response

from hyperscribe.libraries.customization import Customization
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.customization import Customization as UserOptions
from hyperscribe.structures.default_tab import DefaultTab
from tests.helper import MockClass, is_constant


def test_constants():
    tested = Customization
    constants = {
        "CUSTOM_PROMPT_COMMANDS": ["FollowUp", "HistoryOfPresentIllness", "Instruct", "Plan", "ReasonForVisit"],
    }
    assert is_constant(tested, constants)


@patch("hyperscribe.libraries.customization.AwsS3")
@patch.object(Customization, "custom_prompts")
def test_customizations(custom_prompts, aws_s3):
    def reset_mocks():
        custom_prompts.reset_mock()
        aws_s3.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    expected_default = UserOptions(
        custom_prompts=[
            CustomPrompt(command="FollowUp", prompt="", active=False),
            CustomPrompt(command="HistoryOfPresentIllness", prompt="", active=False),
            CustomPrompt(command="Instruct", prompt="", active=False),
            CustomPrompt(command="Plan", prompt="", active=False),
            CustomPrompt(command="ReasonForVisit", prompt="", active=False),
        ],
        ui_default_tab=DefaultTab.TRANSCRIPT,
    )
    expected_custom = UserOptions(
        custom_prompts=[
            CustomPrompt(command="command1", prompt="prompt1", active=True),
            CustomPrompt(command="command2", prompt="prompt2", active=False),
            CustomPrompt(command="command3", prompt="prompt3", active=True),
        ],
        ui_default_tab=DefaultTab.LOGS,
    )

    tested = Customization

    # AWS credentials invalid
    aws_s3.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.access_s3_object.side_effect = []
    custom_prompts.side_effect = []

    result = tested.customizations(credentials, "theCanvasInstance", "theUserId")
    assert result == expected_default

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # AWS credentials valid
    # -- AWS with error
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.access_s3_object.side_effect = [MockClass(status_code=HTTPStatus(500))]
    custom_prompts.side_effect = [[CustomPrompt(command="theCommand", prompt="thePrompt", active=True)]]

    result = tested.customizations(credentials, "theCanvasInstance", "theUserId")
    expected = UserOptions(
        custom_prompts=[CustomPrompt(command="theCommand", prompt="thePrompt", active=True)],
        ui_default_tab=DefaultTab.TRANSCRIPT,
    )
    assert result == expected

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/customizations_theUserId.json"),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert custom_prompts.mock_calls == calls
    reset_mocks()
    # -- AWS no error
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.access_s3_object.side_effect = [
        MockClass(
            status_code=HTTPStatus(200),
            json=lambda: {
                "customPrompts": [
                    {"command": "command1", "prompt": "prompt1", "active": True},
                    {"command": "command2", "prompt": "prompt2", "active": False},
                    {"command": "command3", "prompt": "prompt3"},
                ],
                "uiDefaultTab": "logs",
            },
        )
    ]
    custom_prompts.side_effect = []
    result = tested.customizations(credentials, "theCanvasInstance", "theUserId")
    assert result == expected_custom

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/customizations_theUserId.json"),
    ]
    assert aws_s3.mock_calls == calls
    assert custom_prompts.mock_calls == []
    reset_mocks()


@patch("hyperscribe.libraries.customization.AwsS3")
@patch.object(Customization, "customizations")
def test_save_ui_default_tab(customizations, aws_s3):
    def reset_mocks():
        customizations.reset_mock()
        aws_s3.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    expected_fail = Response(b"Store not ready", status_code=HTTPStatus(401))
    expected_success = Response(b"Saved", status_code=HTTPStatus(200))
    tested = Customization

    # AWS credentials invalid
    customizations.side_effect = []
    aws_s3.return_value.is_ready.side_effect = [False]
    result = tested.save_ui_default_tab(
        credentials,
        "theCanvasInstance",
        "theUserId",
        DefaultTab.ACTIVITY,
    )
    assert result == expected_fail

    assert customizations.mock_calls == []
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # AWS credentials valid
    customizations.side_effect = [
        UserOptions(
            custom_prompts=[
                CustomPrompt(command="command1", prompt="prompt1", active=False),
                CustomPrompt(command="command2", prompt="prompt2", active=True),
            ],
            ui_default_tab=DefaultTab.FEEDBACK,
        )
    ]
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.upload_text_to_s3.side_effect = [expected_success]
    result = tested.save_ui_default_tab(
        credentials,
        "theCanvasInstance",
        "theUserId",
        DefaultTab.ACTIVITY,
    )
    assert result == expected_success

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert customizations.mock_calls == calls
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().upload_text_to_s3(
            "hyperscribe-theCanvasInstance/customizations/customizations_theUserId.json",
            '{"customPrompts": ['
            '{"command": "command1", "prompt": "prompt1", "active": false}, '
            '{"command": "command2", "prompt": "prompt2", "active": true}], '
            '"uiDefaultTab": "activity"}',
        ),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.customization.AwsS3")
@patch.object(Customization, "customizations")
def test_save_custom_prompt(customizations, aws_s3):
    def reset_mocks():
        customizations.reset_mock()
        aws_s3.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    expected_fail = Response(b"Store not ready", status_code=HTTPStatus(401))
    expected_success = Response(b"Saved", status_code=HTTPStatus(200))
    tested = Customization

    # AWS credentials invalid
    customizations.side_effect = []
    aws_s3.return_value.is_ready.side_effect = [False]
    result = tested.save_custom_prompt(
        credentials,
        "theCanvasInstance",
        "theUserId",
        CustomPrompt(command="theCommand", prompt="thePrompt", active=True),
    )
    assert result == expected_fail

    assert customizations.mock_calls == []
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # AWS credentials valid
    # -- command not valid
    customizations.side_effect = []
    aws_s3.return_value.is_ready.side_effect = [True]
    result = tested.save_custom_prompt(
        credentials,
        "theCanvasInstance",
        "theUserId",
        CustomPrompt(command="theCommand", prompt="thePrompt", active=True),
    )
    assert result == expected_fail

    assert customizations.mock_calls == []
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # -- command is valid
    customizations.side_effect = [
        UserOptions(
            custom_prompts=[
                CustomPrompt(command="FollowUp", prompt="promptFollowUp", active=False),
                CustomPrompt(command="HistoryOfPresentIllness", prompt="promptHistoryOfPresentIllness", active=False),
                CustomPrompt(command="Instruct", prompt="promptInstruct", active=False),
                CustomPrompt(command="Plan", prompt="promptPlan", active=False),
                CustomPrompt(command="ReasonForVisit", prompt="promptReasonForVisit", active=False),
            ],
            ui_default_tab=DefaultTab.ACTIVITY,
        )
    ]
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.upload_text_to_s3.side_effect = [expected_success]
    result = tested.save_custom_prompt(
        credentials,
        "theCanvasInstance",
        "theUserId",
        CustomPrompt(command="Instruct", prompt="thePrompt", active=True),
    )
    assert result == expected_success

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert customizations.mock_calls == calls
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().upload_text_to_s3(
            "hyperscribe-theCanvasInstance/customizations/customizations_theUserId.json",
            '{"customPrompts": ['
            '{"command": "FollowUp", "prompt": "promptFollowUp", "active": false}, '
            '{"command": "HistoryOfPresentIllness", "prompt": "promptHistoryOfPresentIllness", "active": false}, '
            '{"command": "Instruct", "prompt": "thePrompt", "active": true}, '
            '{"command": "Plan", "prompt": "promptPlan", "active": false}, '
            '{"command": "ReasonForVisit", "prompt": "promptReasonForVisit", "active": false}], '
            '"uiDefaultTab": "activity"}',
        ),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()


def test_aws_customizations():
    tested = Customization
    result = tested.aws_customizations("theCanvasInstance", "theUserId")
    expected = "hyperscribe-theCanvasInstance/customizations/customizations_theUserId.json"
    assert result == expected


@patch.object(Customization, "customizations")
def test_custom_prompts_as_secret(customizations):
    def reset_mocks():
        customizations.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")

    tested = Customization
    #
    customizations.side_effect = [
        UserOptions(
            ui_default_tab=DefaultTab.ACTIVITY,
            custom_prompts=[],
        )
    ]
    result = tested.custom_prompts_as_secret(credentials, "theCanvasInstance", "theUserId")
    expected = {"CustomPrompts": "[]"}
    assert result == expected

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert customizations.mock_calls == calls
    reset_mocks()

    #
    customizations.side_effect = [
        UserOptions(
            ui_default_tab=DefaultTab.ACTIVITY,
            custom_prompts=[
                CustomPrompt(command="command1", prompt="prompt1", active=True),
                CustomPrompt(command="command2", prompt="prompt2", active=False),
                CustomPrompt(command="command3", prompt="prompt3", active=True),
            ],
        )
    ]
    result = tested.custom_prompts_as_secret(credentials, "theCanvasInstance", "theUserId")
    expected = {
        "CustomPrompts": '[{"command": "command1", "prompt": "prompt1", "active": true}, '
        '{"command": "command2", "prompt": "prompt2", "active": false}, '
        '{"command": "command3", "prompt": "prompt3", "active": true}]',
    }
    assert result == expected

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert customizations.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.customization.AwsS3")
def test_custom_prompts(aws_s3):
    def reset_mocks():
        aws_s3.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    expected_default = [
        CustomPrompt(command="FollowUp", prompt="", active=False),
        CustomPrompt(command="HistoryOfPresentIllness", prompt="", active=False),
        CustomPrompt(command="Instruct", prompt="", active=False),
        CustomPrompt(command="Plan", prompt="", active=False),
        CustomPrompt(command="ReasonForVisit", prompt="", active=False),
    ]
    expected_custom = [
        CustomPrompt(command="command1", prompt="prompt1", active=True),
        CustomPrompt(command="command2", prompt="prompt2", active=False),
        CustomPrompt(command="command3", prompt="prompt3", active=True),
    ]

    tested = Customization

    # AWS credentials invalid
    aws_s3.return_value.is_ready.side_effect = [False]
    result = tested.custom_prompts(credentials, "theCanvasInstance", "theUserId")
    assert result == expected_default

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # AWS credentials valid
    # -- AWS with error twice
    aws_s3.return_value.is_ready.side_effect = [True, True]
    aws_s3.return_value.access_s3_object.side_effect = [
        MockClass(status_code=HTTPStatus(500)),
        MockClass(status_code=HTTPStatus(500)),
    ]
    result = tested.custom_prompts(credentials, "theCanvasInstance", "theUserId")
    assert result == expected_default

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/custom_prompts_theUserId.json"),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/custom_prompts.json"),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # -- AWS with error once
    aws_s3.return_value.is_ready.side_effect = [True, True]
    aws_s3.return_value.access_s3_object.side_effect = [
        MockClass(status_code=HTTPStatus(500)),
        MockClass(
            status_code=HTTPStatus(200),
            json=lambda: [
                {"command": "command1", "prompt": "prompt1", "active": True},
                {"command": "command2", "prompt": "prompt2", "active": False},
                {"command": "command3", "prompt": "prompt3"},
            ],
        ),
    ]
    result = tested.custom_prompts(credentials, "theCanvasInstance", "theUserId")
    assert result == expected_custom

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/custom_prompts_theUserId.json"),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/custom_prompts.json"),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # -- AWS no error
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.access_s3_object.side_effect = [
        MockClass(
            status_code=HTTPStatus(200),
            json=lambda: [
                {"command": "command1", "prompt": "prompt1", "active": True},
                {"command": "command2", "prompt": "prompt2", "active": False},
                {"command": "command3", "prompt": "prompt3"},
            ],
        )
    ]
    result = tested.custom_prompts(credentials, "theCanvasInstance", "theUserId")
    assert result == expected_custom

    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().access_s3_object("hyperscribe-theCanvasInstance/customizations/custom_prompts_theUserId.json"),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()


def test_aws_custom_prompts():
    tested = Customization
    # empty user id
    result = tested.aws_custom_prompts("theCanvasInstance", "")
    expected = "hyperscribe-theCanvasInstance/customizations/custom_prompts.json"
    assert result == expected
    # with user id
    result = tested.aws_custom_prompts("theCanvasInstance", "theUserId")
    expected = "hyperscribe-theCanvasInstance/customizations/custom_prompts_theUserId.json"
    assert result == expected
