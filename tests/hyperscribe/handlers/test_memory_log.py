from datetime import datetime, timezone
from unittest.mock import patch, call

from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.handlers.structures.aws_s3_credentials import AwsS3Credentials
from tests.helper import is_constant


def test_constants():
    tested = MemoryLog
    constants = {
        "ENTRIES": {},
    }
    assert is_constant(tested, constants)


def test_begin_session():
    tested = MemoryLog
    assert "note_uuid" not in tested.ENTRIES
    tested.begin_session("note_uuid")
    assert tested.ENTRIES["note_uuid"] == {}
    #
    tested.ENTRIES["note_uuid"] = {"theLabel": []}
    tested.begin_session("note_uuid")
    assert tested.ENTRIES["note_uuid"] == {"theLabel": []}


def test_end_session():
    tested = MemoryLog

    #
    result = tested.end_session("note_uuid_2")
    expected = ""
    assert result == expected

    #
    tested.ENTRIES = {
        "note_uuid_1": {
            "label3": ["r", "s"],
            "label2": ["x", "y"],
            "label1": ["m", "n"],
        },
        "note_uuid_2": {
            "label1": ["m", "n"],
            "label2": ["x", "y"],
            "label3": ["r", "s"],
        },
        "note_uuid_3": {
            "label2": ["x", "y"],
            "label1": ["m", "n"],
            "label3": [],
        },
        "note_uuid_4": {},
    }
    result = tested.end_session("note_uuid_2")
    expected = "m\nn\nr\ns\nx\ny"
    assert result == expected
    result = tested.end_session("note_uuid_1")
    expected = "m\nn\nr\ns\nx\ny"
    assert result == expected
    result = tested.end_session("note_uuid_3")
    expected = "m\nn\nx\ny"
    assert result == expected
    result = tested.end_session("note_uuid_4")
    expected = ""
    assert result == expected
    #
    assert tested.ENTRIES == {}


def test_instance():
    aws_s3 = AwsS3Credentials(aws_key="theAwsKey", aws_secret="theAwsSecret", region="theRegion", bucket="theBucket")
    tested = MemoryLog
    result = tested.instance("note_uuid", "theLabel", aws_s3)
    assert isinstance(result, MemoryLog)
    assert result.note_uuid == "note_uuid"
    assert result.label == "theLabel"
    assert result.aws_s3 == aws_s3


def test___init__():
    tested = MemoryLog("note_uuid", "theLabel")
    expected = {"note_uuid": {"theLabel": []}}
    assert tested.ENTRIES == expected


@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
def test_log(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    tested = MemoryLog("note_uuid", "theLabel")
    expected = {"note_uuid": {"theLabel": []}}
    assert tested.ENTRIES == expected

    mock_datetime.now.side_effect = [
        datetime(2025, 3, 6, 7, 53, 21, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 11, 53, 37, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 19, 11, 51, tzinfo=timezone.utc),
    ]

    tested.log("message1")
    tested.log("message2")
    tested.log("message3")
    expected = {
        "note_uuid": {
            "theLabel": [
                '2025-03-06T07:53:21+00:00: message1',
                '2025-03-06T11:53:37+00:00: message2',
                '2025-03-06T19:11:51+00:00: message3',

            ],
        },
    }
    assert tested.ENTRIES == expected

    calls = [
        call.now(timezone.utc),
        call.now(timezone.utc),
        call.now(timezone.utc),
    ]
    assert mock_datetime.mock_calls == calls
    reset_mocks()
    MemoryLog.end_session("note_uuid")


@patch("hyperscribe.handlers.memory_log.log")
@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
def test_output(mock_datetime, log):
    def reset_mocks():
        mock_datetime.reset_mock()
        log.reset_mock()

    tested = MemoryLog("note_uuid", "theLabel")
    expected = {"note_uuid": {"theLabel": []}}
    assert tested.ENTRIES == expected

    mock_datetime.now.side_effect = [
        datetime(2025, 3, 6, 7, 53, 21, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 11, 53, 37, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 19, 11, 51, tzinfo=timezone.utc),
    ]

    tested.output("message1")
    tested.output("message2")
    tested.output("message3")
    expected = {
        "note_uuid": {
            "theLabel": [
                '2025-03-06T07:53:21+00:00: message1',
                '2025-03-06T11:53:37+00:00: message2',
                '2025-03-06T19:11:51+00:00: message3',

            ],
        },
    }
    assert tested.ENTRIES == expected

    calls = [
        call.now(timezone.utc),
        call.now(timezone.utc),
        call.now(timezone.utc),
    ]
    assert mock_datetime.mock_calls == calls
    calls = [
        call.info('message1'),
        call.info('message2'),
        call.info('message3'),
    ]
    assert log.mock_calls == calls
    reset_mocks()
    MemoryLog.end_session("note_uuid")


@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
def test_logs(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    tested = MemoryLog("note_uuid", "theLabel")
    result = tested.logs()
    expected = ""
    assert result == expected

    mock_datetime.now.side_effect = [
        datetime(2025, 3, 6, 7, 53, 21, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 11, 53, 37, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 19, 11, 51, tzinfo=timezone.utc),
    ]

    tested.log("message1")
    tested.log("message2")
    tested.log("message3")
    result = tested.logs()
    expected = ('2025-03-06T07:53:21+00:00: message1'
                '\n2025-03-06T11:53:37+00:00: message2'
                '\n2025-03-06T19:11:51+00:00: message3')
    assert result == expected

    calls = [
        call.now(timezone.utc),
        call.now(timezone.utc),
        call.now(timezone.utc),
    ]
    assert mock_datetime.mock_calls == calls
    reset_mocks()
    MemoryLog.end_session("note_uuid")


@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
@patch("hyperscribe.handlers.memory_log.AwsS3")
def test_store_so_far(aws_s3, mock_datetime):
    def reset_mocks():
        aws_s3.reset_mock()
        mock_datetime.reset_mock()

    tested = MemoryLog("note_uuid", "theLabel")
    #
    aws_s3.return_value.is_ready.side_effect = [False]
    mock_datetime.now.side_effect = []
    tested.store_so_far()
    calls = [
        call(AwsS3Credentials(aws_key='', aws_secret='', region='', bucket='')),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    assert mock_datetime.mock_calls == []
    reset_mocks()
    #
    now = datetime(2025, 3, 11, 15, 38, 37, tzinfo=timezone.utc)
    aws_s3.return_value.is_ready.side_effect = [True]
    mock_datetime.now.side_effect = [now]
    tested.store_so_far()
    calls = [
        call(AwsS3Credentials(aws_key='', aws_secret='', region='', bucket='')),
        call().is_ready(),
        call().upload_text_to_s3('2025-03-11/partials/note_uuid/theLabel.log', ''),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()
