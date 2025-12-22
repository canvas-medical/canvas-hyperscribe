from datetime import datetime, timezone
from unittest.mock import patch, call

import hyperscribe.libraries.memory_log as memory_log
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from canvas_sdk.clients.llms import LlmTokens


def test_token_counts():
    with patch.object(memory_log, "PROMPTS", {}):
        tested = MemoryLog

        result = tested.token_counts("noteUuid")
        expected = LlmTokens(prompt=0, generated=0)
        assert result == expected

        memory_log.PROMPTS = {
            "noteUuid_1": LlmTokens(prompt=121, generated=81),
            "noteUuid_2": LlmTokens(prompt=122, generated=82),
        }
        result = tested.token_counts("noteUuid_1")
        expected = LlmTokens(prompt=121, generated=81)
        assert result == expected
        result = tested.token_counts("noteUuid_2")
        expected = LlmTokens(prompt=122, generated=82)
        assert result == expected
        result = tested.token_counts("noteUuid_3")
        expected = LlmTokens(prompt=0, generated=0)
        assert result == expected


def test_end_session():
    with patch.object(memory_log, "ENTRIES", {}):
        with patch.object(memory_log, "PROMPTS", {}):
            tested = MemoryLog

            #
            result = tested.end_session("noteUuid_2")
            expected = ""
            assert result == expected

            #
            memory_log.ENTRIES = {
                "noteUuid_1": {"label3": ["r", "s"], "label2": ["x", "y"], "label1": ["m", "n"]},
                "noteUuid_2": {"label1": ["m", "n"], "label2": ["x", "y"], "label3": ["r", "s"]},
                "noteUuid_3": {"label2": ["x", "y"], "label1": ["m", "n"], "label3": []},
                "noteUuid_4": {},
            }
            memory_log.PROMPTS = {
                "noteUuid_1": LlmTokens(prompt=121, generated=81),
                "noteUuid_2": LlmTokens(prompt=122, generated=82),
                "noteUuid_3": LlmTokens(prompt=123, generated=83),
                "noteUuid_4": LlmTokens(prompt=124, generated=84),
            }
            result = tested.end_session("noteUuid_2")
            expected = "TOTAL Tokens: 122 / 82\n\n\n\nm\nn\n\n\n\nr\ns\n\n\n\nx\ny"
            assert result == expected
            result = tested.end_session("noteUuid_1")
            expected = "TOTAL Tokens: 121 / 81\n\n\n\nm\nn\n\n\n\nr\ns\n\n\n\nx\ny"
            assert result == expected
            result = tested.end_session("noteUuid_3")
            expected = "TOTAL Tokens: 123 / 83\n\n\n\nm\nn\n\n\n\nx\ny"
            assert result == expected
            result = tested.end_session("noteUuid_4")
            expected = "TOTAL Tokens: 124 / 84"
            assert result == expected
            #
            assert memory_log.ENTRIES == {}


def test_dev_null_instance():
    tested = MemoryLog
    result = tested.dev_null_instance()

    assert isinstance(result, MemoryLog)
    expected_identification = IdentificationParameters(
        patient_uuid="",
        note_uuid="",
        provider_uuid="",
        canvas_instance="local",
    )
    assert result.identification == expected_identification
    assert result.label == "local"


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
    assert result.s3_credentials == aws_s3


def test___init__():
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    s3_credentials = AwsS3Credentials(aws_key="", aws_secret="", region="", bucket="")

    with patch.object(memory_log, "ENTRIES", {}):
        with patch.object(memory_log, "PROMPTS", {}):
            _ = MemoryLog(identification, "theLabel")
            expected = {"noteUuid": {"theLabel": []}}
            assert memory_log.ENTRIES == expected
            expected = {"noteUuid": LlmTokens(prompt=0, generated=0)}
            assert memory_log.PROMPTS == expected

            # nothing empty
            memory_log.ENTRIES = {"noteUuid": {"theLabel": []}}
            memory_log.PROMPTS = {"noteUuid": LlmTokens(prompt=0, generated=0)}

            tested = MemoryLog(identification, "theLabel")
            expected = {"noteUuid": {"theLabel": []}}
            assert memory_log.ENTRIES == expected
            expected = {"noteUuid": LlmTokens(prompt=0, generated=0)}
            assert memory_log.PROMPTS == expected

            assert tested.identification == identification
            assert tested.label == "theLabel"
            assert tested.s3_credentials == s3_credentials
            assert tested.current_idx == 0


@patch("hyperscribe.libraries.memory_log.datetime", wraps=datetime)
def test_log(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    with patch.object(memory_log, "ENTRIES", {}):
        tested = MemoryLog(identification, "theLabel")
        expected = {"noteUuid": {"theLabel": []}}
        assert memory_log.ENTRIES == expected

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
                    "2025-03-06T07:53:21+00:00: message1",
                    "2025-03-06T11:53:37+00:00: message2",
                    "2025-03-06T19:11:51+00:00: message3",
                ],
            },
        }
        assert memory_log.ENTRIES == expected

        calls = [call.now(timezone.utc), call.now(timezone.utc), call.now(timezone.utc)]
        assert mock_datetime.mock_calls == calls
        reset_mocks()
        MemoryLog.end_session("noteUuid")


@patch("hyperscribe.libraries.memory_log.log")
@patch("hyperscribe.libraries.memory_log.datetime", wraps=datetime)
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
    with patch.object(memory_log, "ENTRIES", {}):
        tested = MemoryLog(identification, "theLabel")
        expected = {"noteUuid": {"theLabel": []}}
        assert memory_log.ENTRIES == expected

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
                    "2025-03-06T07:53:21+00:00: message1",
                    "2025-03-06T11:53:37+00:00: message2",
                    "2025-03-06T19:11:51+00:00: message3",
                ],
            },
        }
        assert memory_log.ENTRIES == expected

        calls = [call.now(timezone.utc), call.now(timezone.utc), call.now(timezone.utc)]
        assert mock_datetime.mock_calls == calls
        calls = [call.info("message1"), call.info("message2"), call.info("message3")]
        assert log.mock_calls == calls
        reset_mocks()
        MemoryLog.end_session("noteUuid")


@patch("hyperscribe.libraries.memory_log.datetime", wraps=datetime)
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
    result = tested.logs(0, 3)
    expected = ""
    assert result == expected

    mock_datetime.now.side_effect = [
        datetime(2025, 3, 6, 7, 53, 21, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 11, 53, 37, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 19, 11, 51, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 19, 11, 53, tzinfo=timezone.utc),
        datetime(2025, 3, 6, 19, 11, 59, tzinfo=timezone.utc),
    ]

    tested.log("message1")
    tested.log("message2")
    tested.log("message3")
    tested.log("message4")
    tested.log("message5")
    calls = [
        call.now(timezone.utc),
        call.now(timezone.utc),
        call.now(timezone.utc),
        call.now(timezone.utc),
        call.now(timezone.utc),
    ]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    tests = [
        (
            0,
            3,
            "2025-03-06T07:53:21+00:00: message1\n"
            "2025-03-06T11:53:37+00:00: message2\n"
            "2025-03-06T19:11:51+00:00: message3",
        ),
        (1, 3, "2025-03-06T11:53:37+00:00: message2\n2025-03-06T19:11:51+00:00: message3"),
        (
            2,
            5,
            "2025-03-06T19:11:51+00:00: message3\n"
            "2025-03-06T19:11:53+00:00: message4\n"
            "2025-03-06T19:11:59+00:00: message5",
        ),
    ]
    for from_idx, to_idx, expected in tests:
        result = tested.logs(from_idx, to_idx)
        assert result == expected, f"---> {from_idx}, {to_idx}"
        assert mock_datetime.mock_calls == []

    MemoryLog.end_session("noteUuid")


@patch("hyperscribe.libraries.memory_log.AwsS3")
@patch.object(CachedSdk, "get_discussion")
@patch.object(MemoryLog, "log")
def test_store_so_far(log, get_discussion, aws_s3):
    def reset_mocks():
        log.reset_mock()
        get_discussion.reset_mock()
        aws_s3.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    aws_s3_credentials = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucket",
    )
    entries = {
        "noteUuid": {
            "theLabel": [
                "2025-03-06T07:53:21+00:00: message1",
                "2025-03-06T11:53:37+00:00: message2",
                "2025-03-06T19:11:51+00:00: message3",
            ],
        },
    }
    tested = MemoryLog(identification, "theLabel")
    tested.s3_credentials = aws_s3_credentials
    tested.counts = LlmTokens(prompt=127, generated=93)
    with patch.object(memory_log, "ENTRIES", entries):
        #
        aws_s3.return_value.is_ready.side_effect = [False]
        get_discussion.side_effect = []
        tested.store_so_far()
        assert tested.current_idx == 0

        calls = [call(aws_s3_credentials), call().is_ready()]
        assert aws_s3.mock_calls == calls
        assert get_discussion.mock_calls == []
        reset_mocks()
        #
        cached = CachedSdk("theNoteUuid")
        cached.created = datetime(2025, 3, 11, 23, 59, 37, tzinfo=timezone.utc)
        cached.updated = datetime(2025, 3, 12, 0, 38, 21, tzinfo=timezone.utc)
        cached.cycle = 7

        aws_s3.return_value.is_ready.side_effect = [True]
        get_discussion.side_effect = [cached]
        tested.store_so_far()
        assert tested.current_idx == 0  # <-- ensure full log is stored

        calls = [call("---> tokens: 127 / 93")]
        assert log.mock_calls == calls
        calls = [call("noteUuid")]
        assert get_discussion.mock_calls == calls
        calls = [
            call(aws_s3_credentials),
            call().is_ready(),
            call().upload_text_to_s3(
                "hyperscribe-canvasInstance/partials/2025-03-11/noteUuid/07/theLabel.log",
                "2025-03-06T07:53:21+00:00: message1\n"
                "2025-03-06T11:53:37+00:00: message2\n"
                "2025-03-06T19:11:51+00:00: message3",
            ),
        ]
        assert aws_s3.mock_calls == calls
        reset_mocks()


def test_add_consumption():
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    with patch.object(memory_log, "PROMPTS", {}):
        memory_log.PROMPTS = {"noteUuid": LlmTokens(prompt=523, generated=187)}
        tested = MemoryLog(identification, "theLabel")
        tested.counts = LlmTokens(prompt=127, generated=93)

        tested.add_consumption(LlmTokens(prompt=100, generated=50))
        assert tested.counts == LlmTokens(prompt=227, generated=143)
        assert memory_log.PROMPTS == {"noteUuid": LlmTokens(prompt=623, generated=237)}
