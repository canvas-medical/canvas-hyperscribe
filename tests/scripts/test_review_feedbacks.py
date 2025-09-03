from argparse import Namespace
from unittest.mock import patch, call

from _pytest.capture import CaptureResult

from scripts.review_feedbacks import ReviewFeedbacks
from tests.helper import MockClass


@patch("scripts.review_feedbacks.ArgumentParser")
def test__parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    expected = Namespace(customer="theCustomer")
    argument_parser.return_value.parse_args.side_effect = [expected]

    tested = ReviewFeedbacks
    result = tested._parameters()
    assert result == expected

    calls = [
        call(description="List the feedbacks, stored in AWS S3, for a specific customer"),
        call().add_argument(
            "--customer",
            type=str,
            required=True,
            help="The customer as defined in AWS S3",
        ),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("scripts.review_feedbacks.AwsS3")
@patch("scripts.review_feedbacks.HelperEvaluation")
@patch.object(ReviewFeedbacks, "_parameters")
def test_run(parameters, helper, aws_s3, capsys):
    def reset_mocks():
        parameters.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()

    tested = ReviewFeedbacks

    tests = [
        ([], [], "No feedbacks found for theCustomer\n\n"),
        (
            [
                MockClass(key="hyperscribe-theCustomer/feedback/note123abc/20250901-072207"),
                MockClass(key="hyperscribe-theCustomer/feedback/note123xyz/20250901-072209"),
                MockClass(key="hyperscribe-theCustomer/feedback/note123abc/20250902-050532"),
                MockClass(key="hyperscribe-theCustomer/feedback/note123abc/20250902-070707"),
                MockClass(key="hyperscribe-theCustomer/feedback/note123xyz/20250902-111111"),
                MockClass(key="not matching the regex"),
            ],
            [
                MockClass(status_code=200, content=b"content 1 /" * 10),
                MockClass(status_code=200, content=b"content 2 /" * 10),
                MockClass(status_code=200, content=b"content 3 /" * 10),
                MockClass(status_code=500, content=b"content 4 /" * 10),
                MockClass(status_code=200, content=b"content 5 /" * 10),
            ],
            "Feedbacks for theCustomer\n"
            "\n"
            "Note: note123abc\n"
            "Date: 20250901 072207\n"
            "   content 1 /content 1 /content 1\n"
            "   /content 1 /content 1 /content 1\n"
            "   /content 1 /content 1 /content 1\n"
            "   /content 1 /\n"
            "\n"
            "Date: 20250902 050532\n"
            "   content 2 /content 2 /content 2\n"
            "   /content 2 /content 2 /content 2\n"
            "   /content 2 /content 2 /content 2\n"
            "   /content 2 /\n"
            "\n"
            "Date: 20250902 070707\n"
            "   content 3 /content 3 /content 3\n"
            "   /content 3 /content 3 /content 3\n"
            "   /content 3 /content 3 /content 3\n"
            "   /content 3 /\n"
            "\n"
            "\n"
            "Note: note123xyz\n"
            "Date: 20250901 072209\n"
            "Date: 20250902 111111\n"
            "   content 5 /content 5 /content 5\n"
            "   /content 5 /content 5 /content 5\n"
            "   /content 5 /content 5 /content 5\n"
            "   /content 5 /\n"
            "\n",
        ),
    ]
    for feedbacks, accesses, expected_out in tests:
        parameters.side_effect = [Namespace(customer="theCustomer")]
        helper.aws_s3_credentials.side_effect = ["theCredentials"]
        aws_s3.return_value.list_s3_objects.side_effect = [feedbacks]
        aws_s3.return_value.access_s3_object.side_effect = accesses

        tested.run()
        exp_out = CaptureResult(expected_out, err="")
        assert capsys.readouterr() == exp_out

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [call.aws_s3_credentials()]
        assert helper.mock_calls == calls
        calls = [
            call("theCredentials"),
            call().list_s3_objects("hyperscribe-theCustomer/feedback/"),
        ]
        if accesses:
            calls.extend(
                [
                    call().access_s3_object("hyperscribe-theCustomer/feedback/note123abc/20250901-072207"),
                    call().access_s3_object("hyperscribe-theCustomer/feedback/note123abc/20250902-050532"),
                    call().access_s3_object("hyperscribe-theCustomer/feedback/note123abc/20250902-070707"),
                    call().access_s3_object("hyperscribe-theCustomer/feedback/note123xyz/20250901-072209"),
                    call().access_s3_object("hyperscribe-theCustomer/feedback/note123xyz/20250902-111111"),
                ]
            )
        assert aws_s3.mock_calls == calls
        reset_mocks()
