from datetime import datetime

from hyperscribe.structures.aws_s3_object import AwsS3Object
from tests.helper import is_namedtuple


def test_class():
    tested = AwsS3Object
    fields = {"key": str, "size": int, "last_modified": datetime}
    assert is_namedtuple(tested, fields)
