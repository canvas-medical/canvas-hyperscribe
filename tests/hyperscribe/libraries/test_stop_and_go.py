from unittest.mock import patch, call

from hyperscribe.libraries.stop_and_go import StopAndGo


def test___init__():
    tested = StopAndGo("theNoteUuid")
    assert tested.note_uuid == "theNoteUuid"
    assert tested.is_paused is False
    assert tested.is_ended is False
    assert tested.cycle == 1


@patch("hyperscribe.libraries.stop_and_go.get_cache")
def test_save(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    tested = StopAndGo("theNoteUuid")
    tested.cycle = 7
    tested.is_paused = True
    tested.is_ended = True
    tested.save()
    calls = [
        call(),
        call().set(
            "stopAndGo:theNoteUuid",
            {
                "cycle": 7,
                "noteUuid": "theNoteUuid",
                "isPaused": True,
                "isEnded": True,
            },
        ),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


def test_to_json():
    tested = StopAndGo("theNoteUuid")
    tested.cycle = 7
    tested.is_paused = True
    tested.is_ended = True

    result = tested.to_json()
    expected = {
        "cycle": 7,
        "noteUuid": "theNoteUuid",
        "isPaused": True,
        "isEnded": True,
    }
    assert result == expected


@patch("hyperscribe.libraries.stop_and_go.get_cache")
def test_get(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    tested = StopAndGo
    # key exists
    get_cache.return_value.get.side_effect = [
        {
            "cycle": 7,
            "noteUuid": "theNoteUuid",
            "isPaused": True,
            "isEnded": True,
        }
    ]
    result = tested.get("theNoteUuid")
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result.cycle == 7
    assert result.is_ended is True
    assert result.is_paused is True
    calls = [call(), call().get("stopAndGo:theNoteUuid")]
    assert get_cache.mock_calls == calls
    reset_mocks()

    # key does not exist
    get_cache.return_value.get.side_effect = [{}]
    result = tested.get("theNoteUuid")
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result.cycle == 1
    assert result.is_ended is False
    assert result.is_paused is False
    calls = [call(), call().get("stopAndGo:theNoteUuid")]
    assert get_cache.mock_calls == calls
    reset_mocks()


def test_load_from_json():
    tested = StopAndGo
    result = tested.load_from_json(
        {
            "cycle": 7,
            "noteUuid": "theNoteUuid",
            "isPaused": True,
            "isEnded": True,
        }
    )
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result.cycle == 7
    assert result.is_ended is True
    assert result.is_paused is True
