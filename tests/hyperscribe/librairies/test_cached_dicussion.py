from datetime import datetime, timezone
from unittest.mock import patch, call

import hyperscribe.libraries.cached_discussion as cached_discussion
from hyperscribe.libraries.cached_discussion import CachedDiscussion
from hyperscribe.libraries.constants import Constants


@patch("hyperscribe.libraries.cached_discussion.datetime", wraps=datetime)
def test___init__(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    with patch.object(cached_discussion, "CACHED", {}):
        now = datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)
        mock_datetime.now.side_effect = [now]

        tested = CachedDiscussion("noteUuid")
        assert tested.created == now
        assert tested.updated == now
        assert tested.cycle == 1
        assert tested.note_uuid == "noteUuid"
        assert tested.previous_instructions == []
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.libraries.cached_discussion.datetime", wraps=datetime)
def test_add_one(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)
    date_1 = datetime(2025, 2, 4, 7, 48, 33, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0, date_1]

    with patch.object(cached_discussion, "CACHED", {}):
        tested = CachedDiscussion("noteUuid")
        assert tested.created == date_0
        assert tested.updated == date_0
        assert tested.cycle == 1
        assert tested.note_uuid == "noteUuid"
        assert tested.previous_instructions == []
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()

        tested.set_cycle(7)
        assert tested.created == date_0
        assert tested.updated == date_1
        assert tested.cycle == 7
        assert tested.note_uuid == "noteUuid"
        assert tested.previous_instructions == []
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.libraries.cached_discussion.datetime", wraps=datetime)
def test_creation_day(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)
    date_1 = datetime(2025, 2, 4, 7, 48, 33, tzinfo=timezone.utc)
    date_2 = datetime(2025, 2, 4, 7, 48, 37, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0]

    with patch.object(cached_discussion, "CACHED", {}):
        tested = CachedDiscussion("noteUuid")
        for date in [date_0, date_1, date_2]:
            calls = [call.now()]
            assert mock_datetime.mock_calls == calls
            reset_mocks()
            mock_datetime.now.side_effect = [date]

            tested.set_cycle(7)
            assert tested.created == date_0
            assert tested.updated == date
            expected = "2025-02-04"
            result = tested.creation_day()
            assert result == expected



def test_get_discussion():
    with patch.object(cached_discussion, "CACHED", {}):
        tested = CachedDiscussion
        assert cached_discussion.CACHED == {}

        result = tested.get_discussion("noteUuid")
        assert isinstance(result, CachedDiscussion)
        assert cached_discussion.CACHED == {"noteUuid": result}

        result2 = tested.get_discussion("noteUuid")
        assert result == result2
        assert cached_discussion.CACHED == {"noteUuid": result}



@patch("hyperscribe.libraries.cached_discussion.datetime", wraps=datetime)
def test_clear_cache(mock_datetime):
    date_0 = datetime(2025, 2, 4, 7, 18, 21, tzinfo=timezone.utc)
    date_1 = datetime(2025, 2, 4, 7, 18, 33, tzinfo=timezone.utc)
    date_2 = datetime(2025, 2, 4, 7, 28, 22, tzinfo=timezone.utc)
    date_3 = datetime(2025, 2, 4, 7, 48, 27, tzinfo=timezone.utc)
    date_4 = datetime(2025, 2, 4, 7, 48, 37, tzinfo=timezone.utc)
    date_5 = datetime(2025, 2, 4, 7, 58, 37, tzinfo=timezone.utc)

    tested = CachedDiscussion

    with patch.object(cached_discussion, "CACHED", {}):
        with patch.object(Constants, "DISCUSSION_CACHED_DURATION", 30):
            mock_datetime.now.side_effect = [date_0]
            result0 = tested.get_discussion("noteUuid0")
            mock_datetime.now.side_effect = [date_1]
            result1 = tested.get_discussion("noteUuid1")
            mock_datetime.now.side_effect = [date_2]
            result2 = tested.get_discussion("noteUuid2")

            mock_datetime.now.side_effect = [date_2]
            tested.clear_cache()
            expected = {
                "noteUuid0": result0,
                "noteUuid1": result1,
                "noteUuid2": result2,
            }
            assert cached_discussion.CACHED == expected

            mock_datetime.now.side_effect = [date_3]
            tested.clear_cache()
            expected = {
                "noteUuid1": result1,
                "noteUuid2": result2,
            }
            assert cached_discussion.CACHED == expected

            mock_datetime.now.side_effect = [date_4]
            tested.clear_cache()
            expected = {
                "noteUuid2": result2,
            }
            assert cached_discussion.CACHED == expected

            mock_datetime.now.side_effect = [date_5]
            tested.clear_cache()
            assert cached_discussion.CACHED == {}

        with patch.object(Constants, "DISCUSSION_CACHED_DURATION", 10):
            mock_datetime.now.side_effect = [date_0]
            _ = tested.get_discussion("noteUuid0")
            mock_datetime.now.side_effect = [date_1]
            result1 = tested.get_discussion("noteUuid1")
            mock_datetime.now.side_effect = [date_2]
            result2 = tested.get_discussion("noteUuid2")

            mock_datetime.now.side_effect = [date_2]
            tested.clear_cache()
            expected = {
                "noteUuid1": result1,
                "noteUuid2": result2,
            }
            assert cached_discussion.CACHED == expected

            mock_datetime.now.side_effect = [date_3]
            tested.clear_cache()
            assert cached_discussion.CACHED == {}

            mock_datetime.now.side_effect = [date_4]
            tested.clear_cache()
            assert cached_discussion.CACHED == {}

            mock_datetime.now.side_effect = [date_5]
            tested.clear_cache()
            assert cached_discussion.CACHED == {}
