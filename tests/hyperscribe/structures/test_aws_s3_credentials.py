from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from tests.helper import is_namedtuple


def test_class():
    tested = AwsS3Credentials
    fields = {
        "aws_key": str,
        "aws_secret": str,
        "region": str,
        "bucket": str,
    }
    assert is_namedtuple(tested, fields)


def test_from_dictionary():
    tested = AwsS3Credentials
    #
    result = tested.from_dictionary({
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucketLogs": "theBucketLogs",
    })
    expected = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucketLogs",
    )
    assert result == expected
    #
    result = tested.from_dictionary({})
    expected = AwsS3Credentials(
        aws_key="",
        aws_secret="",
        region="",
        bucket="",
    )
    assert result == expected
