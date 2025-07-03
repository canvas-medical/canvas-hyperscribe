from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call, MagicMock
import re
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object
from tests.helper import is_constant


def test_constants():
    tested = AwsS3
    constants = {"ALGORITHM": "AWS4-HMAC-SHA256", "SAFE_CHARACTERS": "-._~"}
    assert is_constant(tested, constants)


def test_querystring():
    test = AwsS3
    tests = [
        ({}, ""),
        (
            {"key-2": "value 2", "key.3": "value 3", "key_1": "value 1", "key~4": "value 4", "key 5": "value 5"},
            "key%205=value%205&key-2=value%202&key.3=value%203&key_1=value%201&key~4=value%204",
        ),
    ]
    for params, expected in tests:
        result = test.querystring(params)
        assert result == expected


def test___init__():
    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    assert test.aws_key == "theKey"
    assert test.aws_secret == "theSecret"
    assert test.region == "theRegion"
    assert test.bucket == "theBucket"


def test_is_ready():
    tests = [
        ("theKey", "theSecret", "theRegion", "theBucket", True),
        ("theKey", "theSecret", "theRegion", "", False),
        ("theKey", "theSecret", "", "theBucket", False),
        ("theKey", "", "theRegion", "theBucket", False),
        ("", "theSecret", "theRegion", "theBucket", False),
    ]
    for aws_key, aws_secret, region, bucket, expected in tests:
        credentials = AwsS3Credentials(aws_key=aws_key, aws_secret=aws_secret, region=region, bucket=bucket)
        test = AwsS3(credentials)
        result = test.is_ready()
        assert result is expected


def test_get_host():
    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    result = test.get_host()
    expected = "theBucket.s3.theRegion.amazonaws.com"
    assert result == expected


def test_get_signature_key():
    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    result = test.get_signature_key("20250507T205533Z", "the\nCanonical\nRequest")
    expected = (
        "20250507/theRegion/s3/aws4_request",
        "687fc36b6c415ba9a62fe9484f50977a41d7eb4fed38c81882f2082b3e68deb3",
    )
    assert result == expected


@patch("hyperscribe.libraries.aws_s3.datetime", wraps=datetime)
def test_headers(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)

    tests = [
        (
            "theObjectKey",
            None,
            None,
            {
                "Host": "theBucket.s3.theRegion.amazonaws.com",
                "x-amz-date": "20250304T042137Z",
                "x-amz-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "Authorization": "AWS4-HMAC-SHA256 Credential=theKey/20250304/theRegion/s3/aws4_request, "
                "SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
                "Signature=b27dbd89b557fa3ab76a2fed7debd220accadf2c3f13e40585fa8a7d2897cd4a",
            },
        ),
        (
            "theObjectKey",
            (b"some data", "theContentType"),
            None,
            {
                "Host": "theBucket.s3.theRegion.amazonaws.com",
                "x-amz-content-sha256": "1307990e6ba5ca145eb35e99182a9bec46531bc54ddf656a602c780fa0240dee",
                "x-amz-date": "20250304T042137Z",
                "Authorization": "AWS4-HMAC-SHA256 Credential=theKey/20250304/theRegion/s3/aws4_request, "
                "SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, "
                "Signature=f7dfb75a719bbf2a32d4eb659e078359aee412bebfc9693374eeb0954cd7d064",
            },
        ),
        (
            "theObjectKey",
            None,
            {"key1": "value1", "key2": "value2", "key3": "value3"},
            {
                "Host": "theBucket.s3.theRegion.amazonaws.com",
                "x-amz-date": "20250304T042137Z",
                "x-amz-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "Authorization": "AWS4-HMAC-SHA256 Credential=theKey/20250304/theRegion/s3/aws4_request, "
                "SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
                "Signature=806e7a20a731ca20c61e303739ec40f85de365de0ffa1aff18cbb66497995a10",
            },
        ),
        (
            "theObjectKey",
            (b"some data", "theContentType"),
            {"key1": "value1", "key2": "value2", "key3": "value3"},
            {
                "Host": "theBucket.s3.theRegion.amazonaws.com",
                "x-amz-content-sha256": "1307990e6ba5ca145eb35e99182a9bec46531bc54ddf656a602c780fa0240dee",
                "x-amz-date": "20250304T042137Z",
                "Authorization": "AWS4-HMAC-SHA256 Credential=theKey/20250304/theRegion/s3/aws4_request, "
                "SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, "
                "Signature=58a0beb8ea42b2523bf13aff8555019e62fc0aadf6ec84a84fdc723a14cea812",
            },
        ),
    ]
    for object_key, data, params, expected in tests:
        now = datetime(2025, 3, 4, 4, 21, 37, tzinfo=timezone.utc)
        mock_datetime.now.side_effect = [now]
        result = test.headers(object_key, data=data, params=params)
        assert result == expected

        calls = [call.now(timezone.utc)]
        assert mock_datetime.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.libraries.aws_s3.requests_get")
@patch.object(AwsS3, "headers")
@patch.object(AwsS3, "is_ready")
def test_access_s3_object(is_ready, headers, requests_get):
    def rest_mocks():
        is_ready.reset_mock()
        headers.reset_mock()
        requests_get.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    # ready
    is_ready.side_effect = [True]
    headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
    requests_get.side_effect = ["theResponse"]
    result = test.access_s3_object("theObjectKey")
    assert result == "theResponse"

    calls = [call()]
    assert is_ready.mock_calls == calls
    calls = [call("theObjectKey")]
    assert headers.mock_calls == calls
    calls = [call("https://theHost/theObjectKey", headers={"Host": "theHost", "someKey": "someValue"})]
    assert requests_get.mock_calls == calls
    rest_mocks()
    # not ready
    is_ready.side_effect = [False]
    headers.side_effect = []
    requests_get.side_effect = []
    result = test.access_s3_object("theObjectKey")
    assert result.status_code is None

    calls = [call()]
    assert is_ready.mock_calls == calls
    assert headers.mock_calls == []
    assert requests_get.mock_calls == []
    rest_mocks()


@patch("hyperscribe.libraries.aws_s3.requests_put")
@patch.object(AwsS3, "headers")
@patch.object(AwsS3, "is_ready")
def test_upload_text_to_s3(is_ready, headers, requests_put):
    def rest_mocks():
        is_ready.reset_mock()
        headers.reset_mock()
        requests_put.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    # ready
    is_ready.side_effect = [True]
    headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
    requests_put.side_effect = ["theResponse"]
    result = test.upload_text_to_s3("theObjectKey", "someData")
    assert result == "theResponse"

    calls = [call()]
    assert is_ready.mock_calls == calls
    calls = [call("theObjectKey", (b"someData", "text/plain"))]
    assert headers.mock_calls == calls
    calls = [
        call(
            "https://theHost/theObjectKey",
            headers={"Host": "theHost", "someKey": "someValue", "Content-Type": "text/plain", "Content-Length": "8"},
            data="someData",
        ),
    ]
    assert requests_put.mock_calls == calls
    rest_mocks()
    # not ready
    is_ready.side_effect = [False]
    headers.side_effect = []
    requests_put.side_effect = []
    result = test.upload_text_to_s3("theObjectKey", "someData")
    assert result.status_code is None

    calls = [call()]
    assert is_ready.mock_calls == calls
    assert headers.mock_calls == []
    assert requests_put.mock_calls == []
    rest_mocks()


@patch("hyperscribe.libraries.aws_s3.requests_put")
@patch.object(AwsS3, "headers")
@patch.object(AwsS3, "is_ready")
def test_upload_binary_to_s3(is_ready, headers, requests_put):
    def rest_mocks():
        is_ready.reset_mock()
        headers.reset_mock()
        requests_put.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    # ready
    is_ready.side_effect = [True]
    headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
    requests_put.side_effect = ["theResponse"]
    result = test.upload_binary_to_s3("theObjectKey", b"someData", "theContentType")
    assert result == "theResponse"

    calls = [call()]
    assert is_ready.mock_calls == calls
    calls = [call("theObjectKey", (b"someData", "theContentType"))]
    assert headers.mock_calls == calls
    calls = [
        call(
            "https://theHost/theObjectKey",
            headers={
                "Host": "theHost",
                "someKey": "someValue",
                "Content-Type": "theContentType",
                "Content-Length": "8",
            },
            data=b"someData",
        ),
    ]
    assert requests_put.mock_calls == calls
    rest_mocks()
    # not ready
    is_ready.side_effect = [False]
    headers.side_effect = []
    requests_put.side_effect = []
    result = test.upload_binary_to_s3("theObjectKey", b"someData", "theContentType")
    assert result.status_code is None

    calls = [call()]
    assert is_ready.mock_calls == calls
    assert headers.mock_calls == []
    assert requests_put.mock_calls == []
    rest_mocks()


@patch("hyperscribe.libraries.aws_s3.requests_get")
@patch.object(AwsS3, "headers")
@patch.object(AwsS3, "is_ready")
def test_list_s3_objects(is_ready, headers, requests_get):
    def rest_mocks():
        is_ready.reset_mock()
        headers.reset_mock()
        requests_get.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    tests = [
        (500, []),
        (
            200,
            [
                AwsS3Object(
                    key="2025-03-03/00616.mp3",
                    last_modified=datetime(2025, 3, 3, 23, 48, 45, tzinfo=timezone.utc),
                    size=4785236,
                ),
                AwsS3Object(
                    key="2025-03-03/00617.mp3",
                    last_modified=datetime(2025, 3, 3, 23, 49, 3, tzinfo=timezone.utc),
                    size=3526124,
                ),
                AwsS3Object(
                    key="from_plugin4",
                    last_modified=datetime(2025, 3, 4, 12, 1, 11, tzinfo=timezone.utc),
                    size=43,
                ),
            ],
        ),
    ]
    for status_code, expected in tests:
        # ready
        is_ready.side_effect = [True]
        headers.side_effect = [{"Host": "theHost", "someKey": "someValue"}]
        with (Path(__file__).parent / "list_s3_files.xml").open("br") as f:
            requests_get.return_value.content = f.read()
        requests_get.return_value.status_code = status_code
        result = test.list_s3_objects("some/prefix")
        assert result == expected

        calls = [call()]
        assert is_ready.mock_calls == calls
        calls = [call("", params={"list-type": 2, "prefix": "some/prefix"})]
        assert headers.mock_calls == calls
        calls = [
            call(
                "https://theHost",
                params={"list-type": 2, "prefix": "some/prefix"},
                headers={"Host": "theHost", "someKey": "someValue"},
            ),
        ]
        assert requests_get.mock_calls == calls
        rest_mocks()
        # not ready
        is_ready.side_effect = [False]
        headers.side_effect = []
        result = test.list_s3_objects("some/prefix")
        assert result == []

        calls = [call()]
        assert is_ready.mock_calls == calls
        assert headers.mock_calls == []
        assert requests_get.mock_calls == []
        rest_mocks()


@patch("hyperscribe.libraries.aws_s3.datetime", wraps=datetime)
@patch.object(AwsS3, "is_ready")
def test_generate_presigned_url(is_ready, mock_datetime):
    def reset_mocks():
        is_ready.reset_mock()
        mock_datetime.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    test = AwsS3(credentials)
    # is ready
    tests = [
        (
            "theObjectKey",
            33,
            "https://theBucket.s3.theRegion.amazonaws.com/theObjectKey?"
            "X-Amz-Algorithm=AWS4-HMAC-SHA256&"
            "X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&"
            "X-Amz-Credential=theKey%2F20250507%2FtheRegion%2Fs3%2Faws4_request&"
            "X-Amz-Date=20250507T140521Z&"
            "X-Amz-Expires=33&"
            "X-Amz-Signature=96628d197eb90cd646871e6cbded7f0c0d1c8354691380bcfd7c93bdd62eb789&"
            "X-Amz-SignedHeaders=host",
        ),
        (
            "theObjectKey",
            57,
            "https://theBucket.s3.theRegion.amazonaws.com/theObjectKey?"
            "X-Amz-Algorithm=AWS4-HMAC-SHA256&"
            "X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&"
            "X-Amz-Credential=theKey%2F20250507%2FtheRegion%2Fs3%2Faws4_request&"
            "X-Amz-Date=20250507T140521Z&"
            "X-Amz-Expires=57&"
            "X-Amz-Signature=ce148c9106fae026717ddee2beff96a8bf232d6a9586d516037339f21847c744&"
            "X-Amz-SignedHeaders=host",
        ),
    ]
    now = datetime(2025, 5, 7, 14, 5, 21, tzinfo=timezone.utc)
    for object_key, expiration, expected in tests:
        is_ready.side_effect = [True]
        mock_datetime.now.side_effect = [now]
        result = test.generate_presigned_url(object_key, expiration)
        assert result == expected
        calls = [call()]
        assert is_ready.mock_calls == calls
        calls = [call.now(timezone.utc)]
        assert mock_datetime.mock_calls == calls
        reset_mocks()
    # is not ready
    is_ready.side_effect = [False]
    mock_datetime.now.side_effect = []
    result = test.generate_presigned_url("theObjectKey", 33)
    expected = ""
    assert result == expected
    calls = [call()]
    assert is_ready.mock_calls == calls
    assert mock_datetime.mock_calls == []
    reset_mocks()

'''
S3 returns IsTruncated=true with NextContinuationToken,
leading to just a second page fetch.
'''
    
@patch("hyperscribe.libraries.aws_s3.requests_get")
@patch.object(AwsS3, "headers")
@patch.object(AwsS3, "is_ready")
def test_list_s3_objects_with_continuation(is_ready, headers, requests_get):
    
    # prepare client
    creds = AwsS3Credentials(
        aws_key="theKey", aws_secret="theSecret",
        region="theRegion", bucket="theBucket"
    )
    client = AwsS3(creds)
    is_ready.return_value = True
    headers.return_value = {"Host": "theHost"}
    xml = (Path(__file__).parent / "list_s3_files.xml").read_text(encoding="utf-8")

    xml1 = re.sub(
        r"<IsTruncated>false</IsTruncated>",
        "<IsTruncated>true</IsTruncated>\n<NextContinuationToken>tok123</NextContinuationToken>",
        xml
    ).encode("utf-8")
    xml2 = xml.encode("utf-8")

    # two mock responses
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.content = xml1

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.content = xml2

    requests_get.side_effect = [resp1, resp2]
    objs = client.list_s3_objects("some/prefix")
    assert len(objs) == 6
    assert all(isinstance(o, AwsS3Object) for o in objs)
    assert headers.mock_calls == [
        call("", params={"list-type": 2, "prefix": "some/prefix"}),
        call("", params={"list-type": 2, "prefix": "some/prefix", "continuation-token": "tok123"}),
    ]
    assert requests_get.mock_calls == [
        call(
            "https://theHost",
            params={"list-type": 2, "prefix": "some/prefix"},
            headers={"Host": "theHost"},
        ),
        call(
            "https://theHost",
            params={"list-type": 2, "prefix": "some/prefix", "continuation-token": "tok123"},
            headers={"Host": "theHost"},
        ),
    ]

'''
Simulates IsTruncated=true, but without a NextContinuationToken, 
should can trigger break after one page. 
'''
@patch("hyperscribe.libraries.aws_s3.requests_get")
@patch.object(AwsS3, "headers")
@patch.object(AwsS3, "is_ready")
def test_list_s3_objects_truncated_without_token(is_ready, headers, requests_get):
    creds = AwsS3Credentials(
        aws_key="theKey", aws_secret="theSecret",
        region="theRegion", bucket="theBucket"
    )
    client = AwsS3(creds)

    is_ready.return_value = True
    headers.return_value = {"Host": "theHost"}

    # load XML and force <IsTruncated>true</IsTruncated> but remove any NextContinuationToken
    xml = (Path(__file__).parent / "list_s3_files.xml").read_text(encoding="utf-8")
    xml_trunc = re.sub(
        r"<IsTruncated>false</IsTruncated>",
        "<IsTruncated>true</IsTruncated>",
        xml
    ).encode("utf-8")

    resp = MagicMock()
    resp.status_code = 200
    resp.content = xml_trunc
    requests_get.return_value = resp

    objs = client.list_s3_objects("some/prefix")
    assert len(objs) == 3
    assert all(isinstance(o, AwsS3Object) for o in objs)
    assert headers.mock_calls == [
        call("", params={"list-type": 2, "prefix": "some/prefix"})
    ]
    assert requests_get.mock_calls == [
        call(
            "https://theHost",
            params={"list-type": 2, "prefix": "some/prefix"},
            headers={"Host": "theHost"},
        )
    ]