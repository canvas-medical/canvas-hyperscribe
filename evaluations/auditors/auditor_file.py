from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from random import randint

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.constants import Constants as EvaluationConstants
from evaluations.datastores.filesystem.case import Case as FileSystemCase
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class AuditorFile(AuditorStore):
    AUDIOS_FOLDER = "audios"
    ERROR_JSON_FILE = "errors.json"
    SUMMARY_JSON_FILE = "summary.json"
    SUMMARY_HTML_FILE = "summary.html"


    @classmethod
    def default_folder_base(cls) -> Path:
        return Path(__file__).parent.parent / "cases"

    def __init__(self, case: str, cycle: int, settings: Settings, s3_credentials: AwsS3Credentials, folder_base: Path) -> None:
        super().__init__(case, cycle, settings, s3_credentials)
        self.folder = folder_base / case

    def case_prepare(self) -> None:
        if self.folder.exists() is False:
            self.folder.mkdir()
        FileSystemCase.upsert(EvaluationCase(
            case_name=self.case,
            description=self.case,
        ))

    def case_update_limited_cache(self, limited_cache: dict) -> None:
        case = FileSystemCase.get(self.case)
        FileSystemCase.upsert(EvaluationCase(
            environment=case.environment,
            patient_uuid=case.patient_uuid,
            limited_cache=limited_cache,
            case_type=case.case_type,
            case_group=case.case_group,
            case_name=case.case_name,
            cycles=case.cycles,
            description=case.description,
        ))

    def case_finalize(self, errors: dict) -> None:
        # update the cycles
        case = FileSystemCase.get(self.case)
        FileSystemCase.upsert(EvaluationCase(
            environment=case.environment,
            patient_uuid=case.patient_uuid,
            limited_cache=case.limited_cache,
            case_type=case.case_type,
            case_group=case.case_group,
            case_name=case.case_name,
            cycles=self.cycle,
            description=case.description,
        ))
        # generate the HTML
        data = self.summarized_generated_commands()
        result = self.folder / self.SUMMARY_JSON_FILE
        with result.open("w") as f:
            json.dump(data, f, indent=2)
        # errors
        if errors:
            result = self.folder / self.ERROR_JSON_FILE
            with result.open("w") as f:
                json.dump(errors, f, indent=2)

    def upsert_audio(self, label: str, audio: bytes) -> None:
        audio_folder = self.folder / self.AUDIOS_FOLDER
        if audio_folder.exists() is False:
            audio_folder.mkdir()

        audio_file = audio_folder / f"{label}.mp3"
        with audio_file.open("wb") as fp:
            fp.write(audio)

    def upsert_json(self, label: str, content: dict) -> None:
        file = self.folder / f"{label}.json"
        if label == EvaluationConstants.AUDIO2TRANSCRIPT and file.exists():
            with file.open("r") as fp:
                content = json.load(fp) | content
        with file.open("w") as fp:
            json.dump(content, fp, indent=2)

    def get_json(self, label: str) -> dict:
        json_file = self.folder / f"{label}.json"
        if json_file.exists():
            with json_file.open("r") as fp:
                return dict(json.load(fp))
        return {}

    def limited_chart(self) -> dict:
        return FileSystemCase.get(self.case).limited_cache

    def transcript(self) -> list[Line]:
        return self.full_transcript().get(self.cycle_key, [])

    def full_transcript(self) -> dict[str, list[Line]]:
        content = self.get_json(EvaluationConstants.AUDIO2TRANSCRIPT)
        return {
            key: Line.load_from_json(lines)
            for key, lines in content.items()
        }

    def note_uuid(self) -> str:
        return f"note{datetime.now().strftime('%Y%m%d%H%M%S')}x{randint(1000, 9999)}"

    @classmethod
    def already_generated(cls, case: str) -> bool:
        for file in (cls.default_folder_base() / case).glob("*.json"):
            if file.stem == EvaluationConstants.AUDIO2TRANSCRIPT:
                continue
            return True
        else:
            return False

    @classmethod
    def reset(cls, case: str, delete_audios: bool) -> None:
        folder = cls.default_folder_base() / case
        for file in folder.glob("*.json"):
            if file.stem == EvaluationConstants.AUDIO2TRANSCRIPT and not delete_audios:
                continue
            file.unlink(True)

        if delete_audios:
            audio_folder = folder / cls.AUDIOS_FOLDER
            if audio_folder.exists():
                for file in audio_folder.glob("*.mp3"):
                    file.unlink(True)
                audio_folder.rmdir()
