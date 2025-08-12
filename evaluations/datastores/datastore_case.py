from __future__ import annotations

from evaluations.auditors.auditor_file import AuditorFile
from evaluations.datastores.filesystem.case import Case as FileSystemCase
from evaluations.datastores.postgres.case import Case as PostgresCase
from evaluations.datastores.postgres.generated_note import GeneratedNote as PostgresGeneratedNote
from evaluations.helper_evaluation import HelperEvaluation


class DatastoreCase:
    @classmethod
    def already_generated(cls, case: str) -> bool:
        postgres_credentials = HelperEvaluation.postgres_credentials()
        if postgres_credentials.is_ready():
            case_id = PostgresCase(postgres_credentials).get_case(case)
            return bool(len(case_id.transcript) > 0 and len(case_id.limited_chart.demographic_str) > 0)

        return AuditorFile.already_generated(case)

    @classmethod
    def delete(cls, case: str, delete_audios: bool) -> None:
        postgres_credentials = HelperEvaluation.postgres_credentials()
        if postgres_credentials.is_ready():
            case_id = PostgresCase(postgres_credentials).get_id(case)
            PostgresGeneratedNote(postgres_credentials).delete_for(case_id)
            if delete_audios:
                PostgresCase(postgres_credentials).update_fields(case_id, {"transcript": {}})
        else:
            AuditorFile.reset(case, delete_audios)

    @classmethod
    def all_names(cls) -> list[str]:
        postgres_credentials = HelperEvaluation.postgres_credentials()
        if postgres_credentials.is_ready():
            return PostgresCase(postgres_credentials).all_names()

        return [case.case_name for case in FileSystemCase.all()]
