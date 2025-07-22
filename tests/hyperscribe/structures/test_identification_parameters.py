from hyperscribe.structures.identification_parameters import IdentificationParameters
from tests.helper import is_namedtuple


def test_class():
    tested = IdentificationParameters
    fields = {"patient_uuid": str, "note_uuid": str, "provider_uuid": str, "canvas_instance": str}
    assert is_namedtuple(tested, fields)


def test_canvas_host():
    tests = [("theCanvasInstance", "https://theCanvasInstance.canvasmedical.com"), ("local", "http://localhost:8000")]

    for canvas_instance, expected in tests:
        tested = IdentificationParameters(
            patient_uuid="_PatientUuid",
            note_uuid="_NoteUuid",
            provider_uuid="_ProviderUuid",
            canvas_instance=canvas_instance,
        )
        result = tested.canvas_host()
        assert result == expected
