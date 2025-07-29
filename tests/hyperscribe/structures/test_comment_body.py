from datetime import datetime, UTC
from unittest.mock import patch, call

from hyperscribe.structures.comment_body import CommentBody
from tests.helper import is_namedtuple


def test_class():
    tested = CommentBody
    fields = {
        "chunk_index": int,
        "note_id": str,
        "patient_id": str,
        "is_paused": bool,
        "created": datetime,
        "finished": datetime | None,
    }
    assert is_namedtuple(tested, fields)


def test_to_dict():
    tested = CommentBody(
        chunk_index=7,
        note_id="theNoteUuid",
        patient_id="thePatientUuid",
        is_paused=True,
        created=datetime(2025, 5, 12, 11, 6, 47, tzinfo=UTC),
        finished=None,
    )
    result = tested.to_dict()
    expected = {
        "chunk_index": 7,
        "created": "2025-05-12T11:06:47+00:00",
        "finished": None,
        "note_id": "theNoteUuid",
        "patient_id": "thePatientUuid",
        "is_paused": True,
    }

    assert result == expected
    #
    tested = CommentBody(
        chunk_index=7,
        note_id="theNoteUuid",
        patient_id="thePatientUuid",
        is_paused=False,
        created=datetime(2025, 5, 12, 23, 49, 47, tzinfo=UTC),
        finished=datetime(2025, 5, 13, 0, 7, 33, tzinfo=UTC),
    )
    result = tested.to_dict()
    expected = {
        "chunk_index": 7,
        "created": "2025-05-12T23:49:47+00:00",
        "finished": "2025-05-13T00:07:33+00:00",
        "note_id": "theNoteUuid",
        "patient_id": "thePatientUuid",
        "is_paused": False,
    }
    assert result == expected


@patch("hyperscribe.structures.comment_body.datetime", wraps=datetime)
def test_load_from_json(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    tested = CommentBody

    tests = [
        (
            {
                "chunk_index": 7,
                "created": "2025-05-12T11:06:47+00:00",
                "finished": "2025-05-12T11:06:53+00:00",
                "note_id": "theNoteUuid",
                "patient_id": "thePatientUuid",
                "is_paused": False,
            },
            CommentBody(
                chunk_index=7,
                note_id="theNoteUuid",
                patient_id="thePatientUuid",
                is_paused=False,
                created=datetime(2025, 5, 12, 11, 6, 47, tzinfo=UTC),
                finished=datetime(2025, 5, 12, 11, 6, 53, tzinfo=UTC),
            ),
            [call.fromisoformat("2025-05-12T11:06:47+00:00"), call.fromisoformat("2025-05-12T11:06:53+00:00")],
        ),
        (
            {
                "chunk_index": 7,
                "created": "2025-05-12T11:06:47+00:00",
                "finished": None,
                "note_id": "theNoteUuid",
                "patient_id": "thePatientUuid",
                "is_paused": True,
            },
            CommentBody(
                chunk_index=7,
                note_id="theNoteUuid",
                patient_id="thePatientUuid",
                is_paused=True,
                created=datetime(2025, 5, 12, 11, 6, 47, tzinfo=UTC),
                finished=None,
            ),
            [call.fromisoformat("2025-05-12T11:06:47+00:00")],
        ),
        (
            {
                "chunk_index": 7,
                "created": None,
                "finished": None,
                "note_id": "theNoteUuid",
                "patient_id": "thePatientUuid",
                "is_paused": False,
            },
            CommentBody(
                chunk_index=7,
                note_id="theNoteUuid",
                patient_id="thePatientUuid",
                is_paused=False,
                created=datetime(2025, 5, 12, 11, 6, 47, tzinfo=UTC),
                finished=None,
            ),
            [call.now(UTC)],
        ),
    ]
    for data, expected, exp_calls in tests:
        mock_datetime.now.side_effect = [datetime(2025, 5, 12, 11, 6, 47, tzinfo=UTC)]
        result = tested.load_from_json(data)
        assert result == expected
        assert mock_datetime.mock_calls == exp_calls
        reset_mocks()
