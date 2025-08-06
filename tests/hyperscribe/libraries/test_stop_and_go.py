from unittest.mock import patch, call

from canvas_sdk.effects import Effect

from hyperscribe.libraries.stop_and_go import StopAndGo


def test___init__():
    tested = StopAndGo("theNoteUuid")
    assert tested.note_uuid == "theNoteUuid"
    assert tested._is_running is False
    assert tested._is_paused is False
    assert tested._is_ended is False
    assert tested._cycle == 1
    assert tested._paused_effects == []


def test_is_running():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_running() is False
    tested.set_running(True)
    assert tested.is_running() is True


def test_is_paused():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_paused() is False
    tested.set_paused(True)
    assert tested.is_paused() is True


def test_is_ended():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_ended() is False
    tested.set_ended(True)
    assert tested.is_ended() is True


def test_cycle():
    tested = StopAndGo("theNoteUuid")
    assert tested.cycle() == 1
    tested.set_cycle(7)
    assert tested.cycle() == 7


def test_paused_effects():
    tested = StopAndGo("theNoteUuid")
    assert tested.paused_effects() == []
    tested.add_paused_effect(Effect(type="LOG", payload="Log1"))
    tested.add_paused_effect(Effect(type="LOG", payload="Log2"))
    tested.add_paused_effect(Effect(type="LOG", payload="Log3"))
    assert tested.paused_effects() == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    tested.reset_paused_effect()
    assert tested.paused_effects() == []


def test_set_running():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_running() is False
    tested.set_running(True)
    assert tested.is_running() is True


def test_set_paused():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_paused() is False
    tested.set_paused(True)
    assert tested.is_paused() is True


def test_set_ended():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_ended() is False
    tested.set_ended(True)
    assert tested.is_ended() is True


def test_set_cycle():
    tested = StopAndGo("theNoteUuid")
    assert tested.cycle() == 1
    tested.set_cycle(7)
    assert tested.cycle() == 7


def test_add_paused_effects():
    tested = StopAndGo("theNoteUuid")
    assert tested.paused_effects() == []
    tested.add_paused_effect(Effect(type="LOG", payload="Log1"))
    tested.add_paused_effect(Effect(type="LOG", payload="Log2"))
    tested.add_paused_effect(Effect(type="LOG", payload="Log3"))
    assert tested.paused_effects() == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    tested.reset_paused_effect()
    assert tested.paused_effects() == []


def test_reset_paused_effect():
    tested = StopAndGo("theNoteUuid")
    assert tested.paused_effects() == []
    tested.add_paused_effect(Effect(type="LOG", payload="Log1"))
    tested.add_paused_effect(Effect(type="LOG", payload="Log2"))
    tested.add_paused_effect(Effect(type="LOG", payload="Log3"))
    assert tested.paused_effects() == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    tested.reset_paused_effect()
    assert tested.paused_effects() == []


@patch("hyperscribe.libraries.stop_and_go.get_cache")
def test_save(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    tested = StopAndGo("theNoteUuid")
    tested._cycle = 7
    tested._is_running = True
    tested._is_paused = True
    tested._is_ended = True
    tested._paused_effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    tested.save()
    calls = [
        call(),
        call().set(
            "stopAndGo:theNoteUuid",
            {
                "cycle": 7,
                "noteUuid": "theNoteUuid",
                "isRunning": True,
                "isPaused": True,
                "isEnded": True,
                "pausedEffects": [
                    {"type": 1, "payload": "Log1"},
                    {"type": 1, "payload": "Log2"},
                    {"type": 1, "payload": "Log3"},
                ],
            },
        ),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


def test_to_json():
    tested = StopAndGo("theNoteUuid")
    tested._cycle = 7
    tested._is_running = True
    tested._is_paused = True
    tested._is_ended = True
    tested._paused_effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    result = tested.to_json()
    expected = {
        "cycle": 7,
        "noteUuid": "theNoteUuid",
        "isRunning": True,
        "isPaused": True,
        "isEnded": True,
        "pausedEffects": [
            {"type": 1, "payload": "Log1"},
            {"type": 1, "payload": "Log2"},
            {"type": 1, "payload": "Log3"},
        ],
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
            "isRunning": True,
            "isPaused": True,
            "isEnded": True,
            "pausedEffects": [
                {"type": 1, "payload": "Log1"},
                {"type": 1, "payload": "Log2"},
                {"type": 1, "payload": "Log3"},
            ],
        }
    ]
    result = tested.get("theNoteUuid")
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result._cycle == 7
    assert result._is_running is True
    assert result._is_ended is True
    assert result._is_paused is True
    assert result._paused_effects == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    calls = [call(), call().get("stopAndGo:theNoteUuid")]
    assert get_cache.mock_calls == calls
    reset_mocks()

    # key does not exist
    get_cache.return_value.get.side_effect = [{}]
    result = tested.get("theNoteUuid")
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result._cycle == 1
    assert result._is_running is False
    assert result._is_ended is False
    assert result._is_paused is False
    assert result._paused_effects == []
    calls = [call(), call().get("stopAndGo:theNoteUuid")]
    assert get_cache.mock_calls == calls
    reset_mocks()


def test_load_from_json():
    tested = StopAndGo
    result = tested.load_from_json(
        {
            "cycle": 7,
            "noteUuid": "theNoteUuid",
            "isRunning": True,
            "isPaused": True,
            "isEnded": True,
            "pausedEffects": [
                {"type": 1, "payload": "Log1"},
                {"type": 1, "payload": "Log2"},
                {"type": 1, "payload": "Log3"},
            ],
        }
    )
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result._cycle == 7
    assert result._is_running is True
    assert result._is_ended is True
    assert result._is_paused is True
    assert result._paused_effects == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
