from http import HTTPStatus
from unittest.mock import patch, call

from canvas_sdk.effects.simple_api import Response

from hyperscribe.libraries.customization import Customization
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.custom_prompt import CustomPrompt
from tests.helper import MockClass, is_constant


def test_constants():
    tested = Customization
    constants = {
        "CUSTOM_PROMPT_COMMANDS": ["FollowUp", "HistoryOfPresentIllness", "Instruct", "Plan", "ReasonForVisit"],
    }
    assert is_constant(tested, constants)


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


@patch("hyperscribe.libraries.customization.AwsS3")
@patch.object(Customization, "custom_prompts")
def test_save_custom_prompt(custom_prompts, aws_s3):
    def reset_mocks():
        custom_prompts.reset_mock()
        aws_s3.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    expected_fail = Response(b"Store not ready", status_code=HTTPStatus(401))
    expected_success = Response(b"Saved", status_code=HTTPStatus(200))
    tested = Customization

    # AWS credentials invalid
    custom_prompts.side_effect = []
    aws_s3.return_value.is_ready.side_effect = [False]
    result = tested.save_custom_prompt(
        credentials,
        "theCanvasInstance",
        CustomPrompt(command="theCommand", prompt="thePrompt", active=True),
        "theUserId",
    )
    assert result == expected_fail

    assert custom_prompts.mock_calls == []
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # AWS credentials valid
    # -- command not valid
    custom_prompts.side_effect = []
    aws_s3.return_value.is_ready.side_effect = [True]
    result = tested.save_custom_prompt(
        credentials,
        "theCanvasInstance",
        CustomPrompt(command="theCommand", prompt="thePrompt", active=True),
        "theUserId",
    )
    assert result == expected_fail

    assert custom_prompts.mock_calls == []
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # -- command is valid
    custom_prompts.side_effect = [
        [
            CustomPrompt(command="FollowUp", prompt="promptFollowUp", active=False),
            CustomPrompt(command="HistoryOfPresentIllness", prompt="promptHistoryOfPresentIllness", active=False),
            CustomPrompt(command="Instruct", prompt="promptInstruct", active=False),
            CustomPrompt(command="Plan", prompt="promptPlan", active=False),
            CustomPrompt(command="ReasonForVisit", prompt="promptReasonForVisit", active=False),
        ]
    ]
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.upload_text_to_s3.side_effect = [expected_success]
    result = tested.save_custom_prompt(
        credentials,
        "theCanvasInstance",
        CustomPrompt(command="Instruct", prompt="thePrompt", active=True),
        "theUserId",
    )
    assert result == expected_success

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert custom_prompts.mock_calls == calls
    calls = [
        call(credentials),
        call().__bool__(),
        call().is_ready(),
        call().upload_text_to_s3(
            "hyperscribe-theCanvasInstance/customizations/custom_prompts_theUserId.json",
            '[{"command": "FollowUp", "prompt": "promptFollowUp", "active": false}, '
            '{"command": "HistoryOfPresentIllness", "prompt": "promptHistoryOfPresentIllness", "active": false}, '
            '{"command": "Instruct", "prompt": "thePrompt", "active": true}, '
            '{"command": "Plan", "prompt": "promptPlan", "active": false}, '
            '{"command": "ReasonForVisit", "prompt": "promptReasonForVisit", "active": false}]',
        ),
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


@patch.object(Customization, "custom_prompts")
def test_custom_prompts_as_secret(custom_prompts):
    def reset_mocks():
        custom_prompts.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")

    tested = Customization
    #
    custom_prompts.side_effect = [[]]
    result = tested.custom_prompts_as_secret(credentials, "theCanvasInstance", "theUserId")
    expected = {"CustomPrompts": "[]"}
    assert result == expected

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert custom_prompts.mock_calls == calls
    reset_mocks()

    #
    custom_prompts.side_effect = [
        [
            CustomPrompt(command="command1", prompt="prompt1", active=True),
            CustomPrompt(command="command2", prompt="prompt2", active=False),
            CustomPrompt(command="command3", prompt="prompt3", active=True),
        ]
    ]
    result = tested.custom_prompts_as_secret(credentials, "theCanvasInstance", "theUserId")
    expected = {
        "CustomPrompts": '[{"command": "command1", "prompt": "prompt1", "active": true}, '
        '{"command": "command2", "prompt": "prompt2", "active": false}, '
        '{"command": "command3", "prompt": "prompt3", "active": true}]',
    }
    assert result == expected

    calls = [call(credentials, "theCanvasInstance", "theUserId")]
    assert custom_prompts.mock_calls == calls
    reset_mocks()
