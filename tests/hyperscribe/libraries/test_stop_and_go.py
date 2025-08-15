from datetime import UTC, datetime
from unittest.mock import patch, call

from canvas_sdk.effects import Effect

from hyperscribe.libraries.stop_and_go import StopAndGo


@patch("hyperscribe.libraries.stop_and_go.datetime", wraps=datetime)
def test___init__(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    mock_datetime.now.side_effect = [datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)]

    tested = StopAndGo("theNoteUuid")
    assert tested.note_uuid == "theNoteUuid"
    assert tested._created == datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)
    assert tested._is_running is False
    assert tested._is_paused is False
    assert tested._is_ended is False
    assert tested._cycle == 1
    assert tested._paused_effects == []
    assert tested._waiting_cycles == []
    assert tested._delay == 0

    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.stop_and_go.datetime", wraps=datetime)
def test_created(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    mock_datetime.now.side_effect = [datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)]

    tested = StopAndGo("theNoteUuid")
    result = tested.created()
    expected = datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)
    assert result == expected

    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


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
    tested.add_paused_effects([Effect(type="LOG", payload="Log1")])
    tested.add_paused_effects([Effect(type="LOG", payload="Log2")])
    tested.add_paused_effects([Effect(type="LOG", payload="Log3")])
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
    result = tested.set_running(True)
    assert result is tested
    assert tested.is_running() is True


def test_set_paused():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_paused() is False
    result = tested.set_paused(True)
    assert result is tested
    assert tested.is_paused() is True


def test_set_ended():
    tested = StopAndGo("theNoteUuid")
    assert tested.is_ended() is False
    result = tested.set_ended(True)
    assert result is tested
    assert tested.is_ended() is True


def test_set_cycle():
    tested = StopAndGo("theNoteUuid")
    assert tested.cycle() == 1
    result = tested.set_cycle(7)
    assert result is tested
    assert tested.cycle() == 7


def test_add_paused_effects():
    tested = StopAndGo("theNoteUuid")
    assert tested.paused_effects() == []
    result = tested.add_paused_effects(
        [
            Effect(type="LOG", payload="Log1"),
            Effect(type="LOG", payload="Log2"),
        ]
    )
    assert result is tested
    result = tested.add_paused_effects([Effect(type="LOG", payload="Log3")])
    assert result is tested
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
    tested.add_paused_effects([Effect(type="LOG", payload="Log1")])
    tested.add_paused_effects([Effect(type="LOG", payload="Log2")])
    tested.add_paused_effects([Effect(type="LOG", payload="Log3")])
    assert tested.paused_effects() == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    result = tested.reset_paused_effect()
    assert result is tested
    assert tested.paused_effects() == []


def test_add_waiting_cycle():
    tested = StopAndGo("theNoteUuid")
    assert tested.waiting_cycles() == []
    result = tested.add_waiting_cycle(5)
    assert result is tested
    assert tested.waiting_cycles() == [5]
    result = tested.add_waiting_cycle(3)
    assert result is tested
    assert tested.waiting_cycles() == [5, 3]
    # adding duplicate should not add again
    result = tested.add_waiting_cycle(5)
    assert result is tested
    assert tested.waiting_cycles() == [5, 3]


@patch.object(StopAndGo, "save")
def test_consume_next_waiting_cycles(save):
    def reset_mocks():
        save.reset_mock()

    tested = StopAndGo("theNoteUuid")
    tested.add_waiting_cycle(5)
    tested.add_waiting_cycle(3)
    tested.add_waiting_cycle(7)

    # consume with save=True
    result = tested.consume_next_waiting_cycles(True)
    expected = True
    assert result == expected
    assert tested.cycle() == 5
    assert tested.waiting_cycles() == [3, 7]

    calls = [call()]
    assert save.mock_calls == calls
    reset_mocks()

    # consume with save=False
    result = tested.consume_next_waiting_cycles(False)
    expected = True
    assert result == expected
    assert tested.cycle() == 3
    assert tested.waiting_cycles() == [7]

    calls = []
    assert save.mock_calls == calls
    reset_mocks()

    # consume last one
    result = tested.consume_next_waiting_cycles(True)
    expected = True
    assert result == expected
    assert tested.cycle() == 7
    assert tested.waiting_cycles() == []

    calls = [call()]
    assert save.mock_calls == calls
    reset_mocks()

    # consume when empty
    result = tested.consume_next_waiting_cycles(True)
    expected = False
    assert result == expected
    assert tested.cycle() == 7
    assert tested.waiting_cycles() == []

    calls = []
    assert save.mock_calls == calls
    reset_mocks()


def test_waiting_cycles():
    tested = StopAndGo("theNoteUuid")
    assert tested.waiting_cycles() == []
    tested.add_waiting_cycle(5)
    tested.add_waiting_cycle(3)
    assert tested.waiting_cycles() == [5, 3]


def test_set_delay():
    tested = StopAndGo("theNoteUuid")
    assert tested._delay == 0
    result = tested.set_delay()
    assert result is tested
    assert tested._delay == 1


@patch("hyperscribe.libraries.stop_and_go.sleep")
def test_consume_delay(sleep):
    def reset_mocks():
        sleep.reset_mock()

    tested = StopAndGo("theNoteUuid")

    tested.consume_delay()
    assert sleep.mock_calls == []
    reset_mocks()

    tested.set_delay()
    tested.consume_delay()
    calls = [call(1)]
    assert sleep.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.stop_and_go.get_cache")
@patch("hyperscribe.libraries.stop_and_go.datetime", wraps=datetime)
def test_save(mock_datetime, get_cache):
    def reset_mocks():
        mock_datetime.reset_mock()
        get_cache.reset_mock()

    mock_datetime.now.side_effect = [datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)]

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
    tested._waiting_cycles = [2, 5, 8]
    tested._delay = 3
    tested.save()
    calls = [
        call(),
        call().set(
            "stopAndGo:theNoteUuid",
            {
                "cycle": 7,
                "noteUuid": "theNoteUuid",
                "created": "2025-08-07T14:01:37.123456+00:00",
                "isRunning": True,
                "isPaused": True,
                "isEnded": True,
                "pausedEffects": [
                    {"type": 1, "payload": "Log1"},
                    {"type": 1, "payload": "Log2"},
                    {"type": 1, "payload": "Log3"},
                ],
                "waitingCycles": [2, 5, 8],
                "delay": 3,
            },
        ),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.stop_and_go.datetime", wraps=datetime)
def test_to_json(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    mock_datetime.now.side_effect = [datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)]

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
    tested._waiting_cycles = [2, 5, 8]
    tested._delay = 3
    result = tested.to_json()
    expected = {
        "cycle": 7,
        "noteUuid": "theNoteUuid",
        "created": "2025-08-07T14:01:37.123456+00:00",
        "isRunning": True,
        "isPaused": True,
        "isEnded": True,
        "pausedEffects": [
            {"type": 1, "payload": "Log1"},
            {"type": 1, "payload": "Log2"},
            {"type": 1, "payload": "Log3"},
        ],
        "waitingCycles": [2, 5, 8],
        "delay": 3,
    }
    assert result == expected
    reset_mocks()


@patch("hyperscribe.libraries.stop_and_go.get_cache")
@patch("hyperscribe.libraries.stop_and_go.datetime", wraps=datetime)
def test_get(mock_datetime, get_cache):
    def reset_mocks():
        mock_datetime.reset_mock()
        get_cache.reset_mock()

    tested = StopAndGo
    # key exists
    get_cache.return_value.get.side_effect = [
        {
            "cycle": 7,
            "noteUuid": "theNoteUuid",
            "created": "2025-08-07T14:01:37.123456+00:00",
            "isRunning": True,
            "isPaused": True,
            "isEnded": True,
            "pausedEffects": [
                {"type": 1, "payload": "Log1"},
                {"type": 1, "payload": "Log2"},
                {"type": 1, "payload": "Log3"},
            ],
            "waitingCycles": [2, 5, 8],
            "delay": 3,
        }
    ]
    result = tested.get("theNoteUuid")
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result._cycle == 7
    assert result._created == datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)
    assert result._is_running is True
    assert result._is_ended is True
    assert result._is_paused is True
    assert result._paused_effects == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    assert result._waiting_cycles == [2, 5, 8]
    assert result._delay == 3
    calls = [call(), call().get("stopAndGo:theNoteUuid")]
    assert get_cache.mock_calls == calls
    reset_mocks()

    # key does not exist
    mock_datetime.now.side_effect = [datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)]
    get_cache.return_value.get.side_effect = [{}]
    result = tested.get("theNoteUuid")
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result._cycle == 1
    assert result._created == datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)
    assert result._is_running is False
    assert result._is_ended is False
    assert result._is_paused is False
    assert result._paused_effects == []
    assert result._waiting_cycles == []
    assert result._delay == 0
    calls = [call(), call().get("stopAndGo:theNoteUuid")]
    assert get_cache.mock_calls == calls
    reset_mocks()


def test_load_from_json():
    tested = StopAndGo
    result = tested.load_from_json(
        {
            "cycle": 7,
            "noteUuid": "theNoteUuid",
            "created": "2025-08-07T14:01:37.123456+00:00",
            "isRunning": True,
            "isPaused": True,
            "isEnded": True,
            "pausedEffects": [
                {"type": 1, "payload": "Log1"},
                {"type": 1, "payload": "Log2"},
                {"type": 1, "payload": "Log3"},
            ],
            "waitingCycles": [2, 5, 8],
            "delay": 3,
        }
    )
    assert isinstance(result, StopAndGo)
    assert result.note_uuid == "theNoteUuid"
    assert result._cycle == 7
    assert result._created == datetime(2025, 8, 7, 14, 1, 37, 123456, tzinfo=UTC)
    assert result._is_running is True
    assert result._is_ended is True
    assert result._is_paused is True
    assert result._paused_effects == [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    assert result._delay == 3
    assert result._waiting_cycles == [2, 5, 8]
