from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.auditors.auditor_file import AuditorFile
from evaluations.auditors.auditor_store import AuditorStore
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_constant, MockFile


def helper_instance() -> tuple[MagicMock, AuditorFile]:
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    s3_credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")

    base_folder = MagicMock()
    case_folder = MagicMock()
    base_folder.__truediv__.return_value = case_folder
    result = AuditorFile("theCase", 7, settings, s3_credentials, base_folder)
    calls = [call.__truediv__("theCase")]
    assert base_folder.mock_calls == calls
    assert case_folder.mock_calls == []
    base_folder.reset_mock()
    case_folder.reset_mock()
    return case_folder, result


def test_constant():
    tested = AuditorFile
    constants = {
        "AUDIOS_FOLDER": "audios",
        "ERROR_JSON_FILE": "errors.json",
        "SUMMARY_JSON_FILE": "summary.json",
        "SUMMARY_HTML_FILE": "summary.html",
    }
    assert is_constant(tested, constants)


def test_auditor_file():
    tested = AuditorFile
    assert issubclass(tested, AuditorStore)


@patch("evaluations.auditors.auditor_file.Path")
def test_default_folder_base(path):
    folder = MagicMock()

    def reset_mock():
        path.reset_mock()
        folder.reset_mock()

    tested = AuditorFile

    path.return_value.parent.parent.__truediv__.side_effect = [folder]
    result = tested.default_folder_base()
    assert result is folder

    directory = Path(__file__).parent.as_posix().replace("/tests", "")
    calls = [call(f"{directory}/auditor_file.py"), call().parent.parent.__truediv__("cases")]
    assert path.mock_calls == calls
    reset_mock()


def test___init__():
    folder, tested = helper_instance()
    assert tested.folder is folder
    assert isinstance(tested.settings, Settings)
    assert isinstance(tested.s3_credentials, AwsS3Credentials)


@patch("evaluations.auditors.auditor_file.FileSystemCase")
def test_case_prepare(filesystem_case):
    folder, tested = helper_instance()

    def reset_mocks():
        folder.reset_mock()
        filesystem_case.reset_mock()

    for exists in [False, True]:
        folder.exists.side_effect = [exists]
        tested.case_prepare()
        calls = [call.exists()]
        if not exists:
            calls.append(call.mkdir())
        assert folder.mock_calls == calls
        calls = [
            call.upsert(
                EvaluationCase(
                    environment="",
                    patient_uuid="",
                    limited_cache={},
                    case_type="general",
                    case_group="common",
                    case_name="theCase",
                    cycles=0,
                    description="theCase",
                ),
            ),
        ]
        assert filesystem_case.mock_calls == calls
        reset_mocks()


@patch("evaluations.auditors.auditor_file.FileSystemCase")
def test_case_update_limited_cache(filesystem_case):
    folder, tested = helper_instance()

    def reset_mocks():
        folder.reset_mock()
        filesystem_case.reset_mock()

    filesystem_case.get.side_effect = [
        EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            limited_cache={"some": "cache"},
            case_type="theCaseType",
            case_group="theCaseGroup",
            case_name="theCase",
            cycles=3,
            description="theDescription",
        ),
    ]
    tested.case_update_limited_cache({"limited": "cache"})
    assert folder.mock_calls == []
    calls = [
        call.get("theCase"),
        call.upsert(
            EvaluationCase(
                environment="theEnvironment",
                patient_uuid="thePatientUuid",
                limited_cache={"limited": "cache"},
                case_type="theCaseType",
                case_group="theCaseGroup",
                case_name="theCase",
                cycles=3,
                description="theDescription",
            ),
        ),
    ]
    assert filesystem_case.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditors.auditor_file.FileSystemCase")
@patch.object(AuditorFile, "summarized_generated_commands")
def test_case_finalize(summarized_generated_commands, filesystem_case):
    folder, tested = helper_instance()

    def reset_mocks():
        folder.reset_mock()
        filesystem_case.reset_mock()
        summarized_generated_commands.reset_mock()

    tests = [({"error1": "value1", "error2": "value2"}, '{\n  "error1": "value1",\n  "error2": "value2"\n}'), ({}, "")]
    for errors, exp_err in tests:
        filesystem_case.get.side_effect = [
            EvaluationCase(
                environment="theEnvironment",
                patient_uuid="thePatientUuid",
                limited_cache={"some": "cache"},
                case_type="theCaseType",
                case_group="theCaseGroup",
                case_name="theCase",
                cycles=3,
                description="theDescription",
            ),
        ]
        buffers = [MockFile(mode="w"), MockFile(mode="w")]
        folder.__truediv__.return_value.open.side_effect = buffers
        summarized_generated_commands.side_effect = [{"summary": "generated"}]

        tested.case_finalize(errors)
        assert buffers[0].content == '{\n  "summary": "generated"\n}'
        assert buffers[1].content == exp_err

        calls = [call.__truediv__("summary.json"), call.__truediv__().open("w")]
        if errors:
            calls.extend([call.__truediv__("errors.json"), call.__truediv__().open("w")])
        assert folder.mock_calls == calls
        calls = [
            call.get("theCase"),
            call.upsert(
                EvaluationCase(
                    environment="theEnvironment",
                    patient_uuid="thePatientUuid",
                    limited_cache={"some": "cache"},
                    case_type="theCaseType",
                    case_group="theCaseGroup",
                    case_name="theCase",
                    cycles=7,
                    description="theDescription",
                ),
            ),
        ]
        assert filesystem_case.mock_calls == calls
        calls = [call()]
        assert summarized_generated_commands.mock_calls == calls
        reset_mocks()


def test_upsert_audio():
    folder, tested = helper_instance()

    mock_dir = MagicMock()
    mock_file = MagicMock()

    def reset_mocks():
        folder.reset_mock()
        mock_dir.reset_mock()
        mock_file.reset_mock()

    for exists in [True, False]:
        buffer = MockFile(mode="bw")
        folder.__truediv__.side_effect = [mock_dir]
        mock_dir.exists.side_effect = [exists]
        mock_dir.__truediv__.side_effect = [mock_file]
        mock_file.open.side_effect = [buffer]

        tested.upsert_audio("theAudioFile", b"theAudioContent")
        assert buffer.content == b"theAudioContent"

        calls = [call.__truediv__("audios")]
        assert folder.mock_calls == calls
        calls = [call.exists()]
        if not exists:
            calls.append(call.mkdir())
        calls.append(call.__truediv__("theAudioFile.mp3"))
        assert mock_dir.mock_calls == calls
        calls = [call.open("wb")]
        assert mock_file.mock_calls == calls
        reset_mocks()


def test_upsert_json():
    folder, tested = helper_instance()

    mock_file = MagicMock()

    def reset_mocks():
        folder.reset_mock()
        mock_file.reset_mock()

    # transcript file
    for exists in [True, False]:
        buffers = [
            MockFile(mode="r", content=json.dumps({"cycle_002": {"key": "data2"}, "cycle_007": {"key": "data7"}})),
            MockFile(mode="w"),
        ]
        folder.__truediv__.side_effect = [mock_file]
        mock_file.exists.side_effect = [exists]
        if exists:
            mock_file.open.side_effect = buffers
        else:
            mock_file.open.side_effect = buffers[1:]

        tested.upsert_json("audio2transcript", {"cycle_007": {"key": "changed"}})
        assert json.loads(buffers[0].content) == {"cycle_002": {"key": "data2"}, "cycle_007": {"key": "data7"}}
        if exists:
            assert json.loads(buffers[1].content) == {"cycle_002": {"key": "data2"}, "cycle_007": {"key": "changed"}}
        else:
            assert json.loads(buffers[1].content) == {"cycle_007": {"key": "changed"}}

        calls = [call.__truediv__("audio2transcript.json")]
        assert folder.mock_calls == calls
        calls = [call.exists()]
        if exists:
            calls.append(call.open("r"))
        calls.append(call.open("w"))
        assert mock_file.mock_calls == calls
        reset_mocks()

    # other file
    buffers = [MockFile(mode="w")]
    folder.__truediv__.side_effect = [mock_file]
    mock_file.open.side_effect = buffers

    tested.upsert_json("something", {"cycle_007": {"key": "changed"}})
    assert json.loads(buffers[0].content) == {"cycle_007": {"key": "changed"}}

    calls = [call.__truediv__("something.json")]
    assert folder.mock_calls == calls
    calls = [call.open("w")]
    assert mock_file.mock_calls == calls
    reset_mocks()


def test_get_json():
    folder, tested = helper_instance()

    mock_file = MagicMock()

    def reset_mocks():
        folder.reset_mock()
        mock_file.reset_mock()

    tests = [(True, {"key": "data"}), (False, {})]
    for exists, expected in tests:
        buffer = MockFile(mode="r", content='{"key":"data"}')
        folder.__truediv__.side_effect = [mock_file]
        mock_file.exists.side_effect = [exists]
        mock_file.open.side_effect = [buffer]

        result = tested.get_json("theLabel")
        assert result == expected
        assert buffer.content == '{"key":"data"}'

        calls = [call.__truediv__("theLabel.json")]
        assert folder.mock_calls == calls
        calls = [call.exists()]
        if exists:
            calls.append(call.open("r"))
        assert mock_file.mock_calls == calls
        reset_mocks()


@patch("evaluations.auditors.auditor_file.FileSystemCase")
def test_limited_chart(filesystem_case):
    folder, tested = helper_instance()

    def reset_mocks():
        folder.reset_mock()
        filesystem_case.reset_mock()

    filesystem_case.get.side_effect = [
        EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            limited_cache={"limited": "cache"},
            case_type="theCaseType",
            case_group="theCaseGroup",
            case_name="theCase",
            cycles=3,
            description="theDescription",
        ),
    ]

    result = tested.limited_chart()
    expected = {"limited": "cache"}
    assert result == expected

    assert folder.mock_calls == []
    calls = [call.get("theCase")]
    assert filesystem_case.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "full_transcript")
def test_transcript(full_transcript):
    folder, tested = helper_instance()

    def reset_mocks():
        folder.reset_mock()
        full_transcript.reset_mock()

    full_transcript.side_effect = [{"cycle_007": [Line(speaker="aSpeaker", text="aText")]}]
    result = tested.transcript()
    expected = [Line(speaker="aSpeaker", text="aText")]
    assert result == expected

    assert folder.mock_calls == []
    calls = [call()]
    assert full_transcript.mock_calls == calls
    reset_mocks()

    full_transcript.side_effect = [{"cycle_006": [Line(speaker="aSpeaker", text="aText")]}]
    result = tested.transcript()
    expected = []
    assert result == expected

    assert folder.mock_calls == []
    calls = [call()]
    assert full_transcript.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "get_json")
def test_full_transcript(get_json):
    folder, tested = helper_instance()

    def reset_mocks():
        folder.reset_mock()
        get_json.reset_mock()

    get_json.side_effect = [
        {
            "cycle_001": [
                {"speaker": "theSpeaker1", "text": "theText1"},
                {"speaker": "theSpeaker2", "text": "theText2"},
                {},
            ],
            "cycle_002": [{"speaker": "theSpeaker3", "text": "theText3"}],
        },
    ]

    result = tested.full_transcript()
    expected = {
        "cycle_001": [
            Line(speaker="theSpeaker1", text="theText1"),
            Line(speaker="theSpeaker2", text="theText2"),
            Line(speaker="", text=""),
        ],
        "cycle_002": [Line(speaker="theSpeaker3", text="theText3")],
    }
    assert result == expected

    assert folder.mock_calls == []
    calls = [call("audio2transcript")]
    assert get_json.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditors.auditor_file.datetime", wraps=datetime)
@patch("evaluations.auditors.auditor_file.randint")
def test_note_uuid(randint_mock, datetime_mock):
    def reset_mocks():
        randint_mock.reset_mock()
        datetime_mock.reset_mock()

    folder, tested = helper_instance()

    mock_now = MagicMock()
    mock_now.strftime.side_effect = ["20250721143045"]
    datetime_mock.now.side_effect = [mock_now]
    randint_mock.side_effect = [5678]

    result = tested.note_uuid()
    expected = "note20250721143045x5678"
    assert result == expected

    assert folder.mock_calls == []
    calls = [call.now()]
    assert datetime_mock.mock_calls == calls
    calls = [call("%Y%m%d%H%M%S")]
    assert mock_now.strftime.mock_calls == calls
    calls = [call(1000, 9999)]
    assert randint_mock.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "default_folder_base")
def test_already_generated(default_folder_base):
    def reset_mocks():
        default_folder_base.reset_mock()

    tested = AuditorFile

    exp_calls = [call(), call().__truediv__("theCase"), call().__truediv__().glob("*.json")]

    # no file exists -> not counted as generated
    default_folder_base.return_value.__truediv__.return_value.glob.side_effect = [[]]
    result = tested.already_generated("theCase")
    assert result is False
    assert default_folder_base.mock_calls == exp_calls
    reset_mocks()

    # transcript exists -> not counted as generated
    default_folder_base.return_value.__truediv__.return_value.glob.side_effect = [
        [Path("/some/where/audio2transcript.json")],
    ]
    result = tested.already_generated("theCase")
    assert result is False
    assert default_folder_base.mock_calls == exp_calls
    reset_mocks()

    # other file exists -> counted as generated
    default_folder_base.return_value.__truediv__.return_value.glob.side_effect = [[Path("/some/where/any.json")]]
    result = tested.already_generated("theCase")
    assert result is True
    assert default_folder_base.mock_calls == exp_calls
    reset_mocks()


@patch.object(AuditorFile, "default_folder_base")
def test_reset(default_folder_base):
    mock_json_files = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    mock_mp3_files = [MagicMock(), MagicMock()]
    mock_audio_dir = MagicMock()

    def reset_mocks():
        default_folder_base.reset_mock()
        mock_audio_dir.reset_mock()
        for idx, item in enumerate(mock_json_files):
            item.reset_mock()
            if idx == 1:
                item.stem = "audio2transcript"
            else:
                item.stem = f"file{idx:02d}"

        for idx, item in enumerate(mock_mp3_files):
            item.reset_mock()

    reset_mocks()

    tested = AuditorFile

    for delete_audios in [True, False]:
        for audio_exists in [True, False]:
            default_folder_base.return_value.__truediv__.return_value.glob.side_effect = [mock_json_files]
            default_folder_base.return_value.__truediv__.return_value.__truediv__.side_effect = [mock_audio_dir]
            mock_audio_dir.exists.side_effect = [audio_exists]
            mock_audio_dir.glob.side_effect = [mock_mp3_files]

            tested.reset("theCase", delete_audios)

            calls = [call(), call().__truediv__("theCase"), call().__truediv__().glob("*.json")]
            if delete_audios:
                calls.append(call().__truediv__().__truediv__("audios"))
            assert default_folder_base.mock_calls == calls
            for num, file in enumerate(mock_json_files):
                calls = []
                if num != 1 or delete_audios:
                    calls = [call.unlink(True)]
                assert file.mock_calls == calls

            calls = []
            if delete_audios:
                calls.append(call.exists())
                if audio_exists:
                    calls.append(call.glob("*.mp3"))
                    calls.append(call.rmdir())
            assert mock_audio_dir.mock_calls == calls
            for num, file in enumerate(mock_mp3_files):
                calls = []
                if delete_audios and audio_exists:
                    calls = [call.unlink(True)]
                assert file.mock_calls == calls

            reset_mocks()
