from datetime import datetime, timezone
from unittest.mock import patch, call

from hyperscribe.handlers.cached_discussion import CachedDiscussion
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from tests.helper import is_constant


def test_constants():
    tested = MemoryLog
    constants = {
        "ENTRIES": {},
    }
    assert is_constant(tested, constants)


def test_begin_session():
    tested = MemoryLog
    assert "noteUuid" not in tested.ENTRIES
    tested.begin_session("noteUuid")
    assert tested.ENTRIES["noteUuid"] == {}
    #
    tested.ENTRIES["noteUuid"] = {"theLabel": []}
    tested.begin_session("noteUuid")
    assert tested.ENTRIES["noteUuid"] == {"theLabel": []}


def test_end_session():
    tested = MemoryLog

    #
    result = tested.end_session("noteUuid_2")
    expected = ""
    assert result == expected

    #
    tested.ENTRIES = {
        "noteUuid_1": {
            "label3": ["r", "s"],
            "label2": ["x", "y"],
            "label1": ["m", "n"],
        },
        "noteUuid_2": {
            "label1": ["m", "n"],
            "label2": ["x", "y"],
            "label3": ["r", "s"],
        },
        "noteUuid_3": {
            "label2": ["x", "y"],
            "label1": ["m", "n"],
            "label3": [],
        },
        "noteUuid_4": {},
    }
    result = tested.end_session("noteUuid_2")
    expected = "m\nn\nr\ns\nx\ny"
    assert result == expected
    result = tested.end_session("noteUuid_1")
    expected = "m\nn\nr\ns\nx\ny"
    assert result == expected
    result = tested.end_session("noteUuid_3")
    expected = "m\nn\nx\ny"
    assert result == expected
    result = tested.end_session("noteUuid_4")
    expected = ""
    assert result == expected
    #
    assert tested.ENTRIES == {}


def test_instance():
    aws_s3 = AwsS3Credentials(aws_key="theAwsKey", aws_secret="theAwsSecret", region="theRegion", bucket="theBucket")
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    tested = MemoryLog
    result = tested.instance(identification, "theLabel", aws_s3)
    assert isinstance(result, MemoryLog)
    assert result.identification == identification
    assert result.label == "theLabel"
    assert result.aws_s3 == aws_s3


def test___init__():
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    tested = MemoryLog(identification, "theLabel")
    expected = {"noteUuid": {"theLabel": []}}
    assert tested.ENTRIES == expected


@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
def test_log(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    tested = MemoryLog(identification, "theLabel")
    expected = {"noteUuid": {"theLabel": []}}
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
        "noteUuid": {
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
    MemoryLog.end_session("noteUuid")


@patch("hyperscribe.handlers.memory_log.log")
@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
def test_output(mock_datetime, log):
    def reset_mocks():
        mock_datetime.reset_mock()
        log.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    tested = MemoryLog(identification, "theLabel")
    expected = {"noteUuid": {"theLabel": []}}
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
        "noteUuid": {
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
    MemoryLog.end_session("noteUuid")


@patch("hyperscribe.handlers.memory_log.datetime", wraps=datetime)
def test_logs(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    tested = MemoryLog(identification, "theLabel")
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
    MemoryLog.end_session("noteUuid")


@patch.object(CachedDiscussion, "get_discussion")
@patch("hyperscribe.handlers.memory_log.AwsS3")
def test_store_so_far(aws_s3, get_discussion):
    def reset_mocks():
        aws_s3.reset_mock()
        get_discussion.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    tested = MemoryLog(identification, "theLabel")
    #
    aws_s3.return_value.is_ready.side_effect = [False]
    get_discussion.side_effect = []
    tested.store_so_far()
    calls = [
        call(AwsS3Credentials(aws_key='', aws_secret='', region='', bucket='')),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    assert get_discussion.mock_calls == []
    reset_mocks()
    #
    cached = CachedDiscussion("theNoteUuid")
    cached.created = datetime(2025, 3, 11, 23, 59, 37, tzinfo=timezone.utc)
    cached.updated = datetime(2025, 3, 12, 0, 38, 21, tzinfo=timezone.utc)
    cached.count = 7

    aws_s3.return_value.is_ready.side_effect = [True]
    get_discussion.side_effect = [cached]
    tested.store_so_far()
    calls = [
        call(AwsS3Credentials(aws_key='', aws_secret='', region='', bucket='')),
        call().is_ready(),
        call().upload_text_to_s3("canvasInstance/2025-03-11/partials/noteUuid/06/theLabel.log", ""),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call("noteUuid")]
    assert get_discussion.mock_calls == calls
    reset_mocks()
