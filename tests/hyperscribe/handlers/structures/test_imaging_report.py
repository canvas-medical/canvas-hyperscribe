from hyperscribe.handlers.structures.imaging_report import ImagingReport
from tests.helper import is_namedtuple


def test_class():
    tested = ImagingReport
    fields = {
        "code": str,
        "name": str,
    }
    assert is_namedtuple(tested, fields)
