from datetime import UTC, datetime

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import Application
from canvas_sdk.templates import render_to_string

from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials


class Progress(Application):
    def on_open(self) -> Effect:
        content = "invalid context"
        if patient_uuid := self.context.get("patient", {}).get("id", ""):
            canvas_instance = self.environment[Constants.CUSTOMER_IDENTIFIER].strip()
            aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)
            log_path = f"https://{Constants.INFORMANT_AWS_BUCKET}.s3.{aws_s3.region}.amazonaws.com/{canvas_instance}/progresses/{patient_uuid}.log"
            content = render_to_string(
                "handlers/progress/progress.html",
                {
                    "aws_s3_path": log_path,
                    "message_after_date": datetime.now(UTC).isoformat(),
                    "message_end_flag": Constants.INFORMANT_END_OF_MESSAGES,
                },
            )

        return LaunchModalEffect(
            content=content,
            target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE,
        ).apply()
