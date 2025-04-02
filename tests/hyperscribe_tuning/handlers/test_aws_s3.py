from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call

from hyperscribe_tuning.handlers.aws_s3 import AwsS3


def test___init__():
    test = AwsS3("theKey", "theSecret", "theRegion", "theBucket")
    assert test.aws_key_id == "theKey"
    assert test.aws_secret == "theSecret"
    assert test.region == "theRegion"
    assert test.bucket == "theBucket"


@patch("hyperscribe_tuning.handlers.aws_s3.datetime", wraps=datetime)
def test_headers(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    test = AwsS3("theKey", "theSecret", "theRegion", "theBucket")

    tests = [
        ("theObjectKey", None, {
            'Host': 'theBucket.s3.theRegion.amazonaws.com',
            'x-amz-date': '20250304T042137Z',
            'x-amz-content-sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
            'Authorization': 'AWS4-HMAC-SHA256 Credential=theKey/20250304/theRegion/s3/aws4_request, '
                             'SignedHeaders=host;x-amz-content-sha256;x-amz-date, '
                             'Signature=b27dbd89b557fa3ab76a2fed7debd220accadf2c3f13e40585fa8a7d2897cd4a',
        }),
        ("theObjectKey", (b"some data", "theContentType"), {
            'Host': 'theBucket.s3.theRegion.amazonaws.com',
            'x-amz-content-sha256': '1307990e6ba5ca145eb35e99182a9bec46531bc54ddf656a602c780fa0240dee',
            'x-amz-date': '20250304T042137Z',
            'Authorization': 'AWS4-HMAC-SHA256 Credential=theKey/20250304/theRegion/s3/aws4_request, '
                             'SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, '
                             'Signature=f7dfb75a719bbf2a32d4eb659e078359aee412bebfc9693374eeb0954cd7d064',
        }),
    ]
    for object_key, data, expected in tests:
        now = datetime(2025, 3, 4, 4, 21, 37, tzinfo=timezone.utc)
        mock_datetime.now.side_effect = [now]
        result = test.headers(object_key, data)
        assert result == expected

        calls = [call.now(timezone.utc)]
        assert mock_datetime.mock_calls == calls
        reset_mocks()


@patch("hyperscribe_tuning.handlers.aws_s3.requests_get")
@patch.object(AwsS3, "headers")
def test_access_s3_object(headers, requests_get):
    def rest_mocks():
        headers.reset_mock()
        requests_get.reset_mock()

    test = AwsS3("theKey", "theSecret", "theRegion", "theBucket")
    headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
    requests_get.side_effect = ["theResponse"]
    result = test.access_s3_object("theObjectKey")
    assert result == "theResponse"

    calls = [call('theObjectKey')]
    assert headers.mock_calls == calls
    calls = [call(
        'https://theHost/theObjectKey',
        headers={'Host': 'theHost', 'someKey': 'someValue'},
    )]
    assert requests_get.mock_calls == calls
    rest_mocks()


@patch("hyperscribe_tuning.handlers.aws_s3.requests_put")
@patch.object(AwsS3, "headers")
def test_upload_text_to_s3(headers, requests_put):
    def rest_mocks():
        headers.reset_mock()
        requests_put.reset_mock()

    test = AwsS3("theKey", "theSecret", "theRegion", "theBucket")

    headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
    requests_put.side_effect = ["theResponse"]
    result = test.upload_text_to_s3("theObjectKey", "someData")
    assert result == "theResponse"

    calls = [call('theObjectKey', (b'someData', "text/plain"))]
    assert headers.mock_calls == calls
    calls = [call(
        'https://theHost/theObjectKey',
        headers={
            'Host': 'theHost',
            'someKey': 'someValue',
            'Content-Type': "text/plain",
            'Content-Length': '8',
        },
        data='someData',
    )]
    assert requests_put.mock_calls == calls
    rest_mocks()


@patch("hyperscribe_tuning.handlers.aws_s3.requests_put")
@patch.object(AwsS3, "headers")
def test_upload_binary_to_s3(headers, requests_put):
    def rest_mocks():
        headers.reset_mock()
        requests_put.reset_mock()

    test = AwsS3("theKey", "theSecret", "theRegion", "theBucket")
    headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
    requests_put.side_effect = ["theResponse"]
    result = test.upload_binary_to_s3("theObjectKey", b"someData", "theContentType")
    assert result == "theResponse"

    calls = [call('theObjectKey', (b'someData', 'theContentType'))]
    assert headers.mock_calls == calls
    calls = [call(
        'https://theHost/theObjectKey',
        headers={
            'Host': 'theHost',
            'someKey': 'someValue',
            'Content-Type': 'theContentType',
            'Content-Length': '8',
        },
        data=b'someData',
    )]
    assert requests_put.mock_calls == calls
    rest_mocks()


@patch("hyperscribe_tuning.handlers.aws_s3.requests_get")
@patch.object(AwsS3, "headers")
def test_list_s3_objects(headers, requests_get):
    def rest_mocks():
        headers.reset_mock()
        requests_get.reset_mock()

    test = AwsS3("theKey", "theSecret", "theRegion", "theBucket")

    tests = [
        (500, []),
        (200, [
            {
                'key': '2025-03-03/00616.mp3',
                'lastModified': '2025-03-03T23:48:45.000Z',
                'size': 4785236,
            },
            {
                'key': '2025-03-03/00617.mp3',
                'lastModified': '2025-03-03T23:49:03.000Z',
                'size': 3526124,
            },
            {
                'key': 'from_plugin4',
                'lastModified': '2025-03-04T12:01:11.000Z',
                'size': 43,
            },
        ]),
    ]
    for status_code, expected in tests:
        headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
        with (Path(__file__).parent / "list_s3_files.xml").open("br") as f:
            requests_get.return_value.content = f.read()
        requests_get.return_value.status_code = status_code
        result = test.list_s3_objects()
        assert result == expected

        calls = [call("")]
        assert headers.mock_calls == calls
        calls = [call(
            'https://theHost',
            headers={'Host': 'theHost', 'someKey': 'someValue'},
        )]
        assert requests_get.mock_calls == calls
        rest_mocks()
