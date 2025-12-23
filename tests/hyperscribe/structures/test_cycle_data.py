from types import SimpleNamespace
from unittest.mock import patch, MagicMock, call

import pytest

from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.cycle_data import CycleData
from hyperscribe.structures.cycle_data_source import CycleDataSource
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line
from tests.helper import is_namedtuple


def test_class() -> None:
    tested = CycleData
    fields = {
        "audio": bytes,
        "transcript": list[Line],
        "source": CycleDataSource,
    }
    assert is_namedtuple(tested, fields)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(CycleDataSource.AUDIO, True, id="audio"),
        pytest.param(CycleDataSource.TRANSCRIPT, False, id="transcript"),
    ],
)
def test_is_audio(source: CycleDataSource, expected: bool) -> None:
    tested = CycleData(audio=b"", transcript=[], source=source)
    result = tested.is_audio()
    assert result == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(CycleDataSource.AUDIO, 8, id="audio"),
        pytest.param(CycleDataSource.TRANSCRIPT, 3, id="transcript"),
    ],
)
def test_length(source: CycleDataSource, expected: int) -> None:
    tested = CycleData(
        audio=b"theAudio",
        transcript=[
            Line(speaker="theSpeaker0", text="theText0"),
            Line(speaker="theSpeaker0", text="theText1"),
            Line(speaker="theSpeaker1", text="theText2"),
        ],
        source=source,
    )
    result = tested.length()
    assert result == expected


def test_s3_key_path() -> None:
    tested = CycleData
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    result = tested.s3_key_path(identification, 37)
    expected = "hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"
    assert result == expected


def test_content_type_text() -> None:
    tested = CycleData
    result = tested.content_type_text()
    expected = "text/plain"
    assert result == expected


@pytest.mark.parametrize(
    ("is_ready", "side_effects", "expected", "exp_sleep_calls", "exp_s3_calls"),
    [
        pytest.param(
            False,
            [],
            CycleData(audio=b"", transcript=[], source=CycleDataSource.TRANSCRIPT),
            [],
            [call.is_ready()],
            id="aws_s3_no_ready",
        ),
        pytest.param(
            True,
            [
                SimpleNamespace(status_code=200, headers={"content-type": "some/audio"}, content=b"theAudio"),
            ],
            CycleData(audio=b"theAudio", transcript=[], source=CycleDataSource.AUDIO),
            [],
            [
                call.is_ready(),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
            ],
            id="aws_s3_ready_no_error_audio",
        ),
        pytest.param(
            True,
            [
                SimpleNamespace(status_code=200, headers={"content-type": "text/plain"}, text="theText"),
            ],
            CycleData(
                audio=b"",
                transcript=[Line(speaker="Clinician", text="theText")],
                source=CycleDataSource.TRANSCRIPT,
            ),
            [],
            [
                call.is_ready(),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
            ],
            id="aws_s3_ready_no_error_text",
        ),
        pytest.param(
            True,
            [
                SimpleNamespace(status_code=501),
                SimpleNamespace(status_code=502),
                SimpleNamespace(status_code=200, headers={"content-type": "text/plain"}, text="theText"),
            ],
            CycleData(
                audio=b"",
                transcript=[Line(speaker="Clinician", text="theText")],
                source=CycleDataSource.TRANSCRIPT,
            ),
            [call(3), call(3)],
            [
                call.is_ready(),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
            ],
            id="aws_s3_ready_2_errors_text",
        ),
        pytest.param(
            True,
            [
                SimpleNamespace(status_code=501),
                SimpleNamespace(status_code=502),
                SimpleNamespace(status_code=503),
            ],
            CycleData(audio=b"", transcript=[], source=CycleDataSource.TRANSCRIPT),
            [call(3), call(3), call(3)],
            [
                call.is_ready(),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
                call.access_s3_object("hyperscribe-canvasInstance/cycle_data/noteUuid/cycle_037"),
            ],
            id="aws_s3_ready_3_errors",
        ),
    ],
)
@patch("hyperscribe.structures.cycle_data.sleep")
@patch("hyperscribe.structures.cycle_data.AwsS3")
def test_from_s3(
    aws_s3: MagicMock,
    sleep: MagicMock,
    is_ready: bool,
    side_effects: list,
    expected: CycleData,
    exp_sleep_calls: list,
    exp_s3_calls: list,
) -> None:
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
    client_s3 = MagicMock()
    client_s3.is_ready.side_effect = [is_ready]
    client_s3.access_s3_object.side_effect = side_effects
    aws_s3.side_effect = [client_s3]

    tested = CycleData
    result = tested.from_s3(aws_s3_credentials, identification, 37)
    assert result == expected

    calls = [call(aws_s3_credentials)]
    assert aws_s3.mock_calls == calls
    assert sleep.mock_calls == exp_sleep_calls
    assert client_s3.mock_calls == exp_s3_calls
