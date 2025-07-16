from argparse import ArgumentParser, Namespace

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants


class BuilderAuditUrl:

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Generate the URL to access the audit logs.")
        parser.add_argument("--audit", action="store_true")
        parser.add_argument("--patient", required=True, help="Patient UUID")
        parser.add_argument("--note", required=True, help="Note UUID")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        cls.presigned_url(parameters.patient, parameters.note)

    @classmethod
    def presigned_url(cls, patient_uuid: str, note_uuid: str) -> None:
        client_s3 = AwsS3(HelperEvaluation.aws_s3_credentials())
        if client_s3.is_ready():
            presigned_url = Authenticator.presigned_url(
                HelperEvaluation.settings().api_signing_key,
                f"{Constants.PLUGIN_API_BASE_ROUTE}/reviewer",
                {
                    "patient_id": patient_uuid,
                    "note_id": note_uuid,
                },
            )
            print("audits can be seen with:")
            print("")
            print(f"{HelperEvaluation.get_canvas_host()}{presigned_url}")
            print("")
            print("to regenerate the URL, run the command:")
            print(f" uv run python case_builder.py --audit --patient {patient_uuid} --note {note_uuid}")
            print("")
        else:
            print("audits cannot be seen with without proper AWS S3 credentials")
