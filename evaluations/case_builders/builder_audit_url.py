from argparse import ArgumentParser, Namespace

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.handlers.reviewer_button import ReviewerButton
from hyperscribe.libraries.aws_s3 import AwsS3


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
        aws_s3_credentials = HelperEvaluation.aws_s3_credentials()
        client_s3 = AwsS3(aws_s3_credentials)
        if client_s3.is_ready():
            canvas_instance = HelperEvaluation.get_canvas_instance()
            host = f"https://{canvas_instance}"
            if canvas_instance == "localhost":
                host = f"http://{canvas_instance}:8000"

            presigned_url = ReviewerButton.presigned_url(
                patient_uuid,
                note_uuid,
                aws_s3_credentials.aws_secret,
            )
            print("audits can be seen with:")
            print("")
            print(f"{host}{presigned_url}")
            print("")
            print("to regenerate the URL, run the command:")
            print(f" uv run python case_builders.py --audit --patient {patient_uuid} --note {note_uuid}")
            print("")
        else:
            print("audits cannot be seen with without proper AWS S3 credentials")
