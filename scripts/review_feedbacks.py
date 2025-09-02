import textwrap
from argparse import ArgumentParser, Namespace
from http import HTTPStatus
from re import compile as re_compile, match as re_match

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.aws_s3 import AwsS3


class ReviewFeedbacks:
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="List the feedbacks, stored in AWS S3, for a specific customer")
        parser.add_argument(
            "--customer",
            type=str,
            required=True,
            help="The customer as defined in AWS S3",
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        s3_credentials = HelperEvaluation.aws_s3_credentials()
        client_s3 = AwsS3(s3_credentials)

        parameters = cls._parameters()
        feedbacks = [f.key for f in client_s3.list_s3_objects(f"hyperscribe-{parameters.customer}/feedback/")]
        feedbacks.sort()
        if not feedbacks:
            print(f"No feedbacks found for {parameters.customer}")
            print("")
            return

        print(f"Feedbacks for {parameters.customer}")

        pattern = re_compile(rf"hyperscribe-{parameters.customer}/feedback/([a-z0-9-]+)/(\d+)-(\d+)")
        wrapper = textwrap.TextWrapper(
            width=40,
            break_long_words=True,
            break_on_hyphens=True,
            initial_indent=" " * 3,
            subsequent_indent=" " * 3,
        )
        current_note = ""
        for feedback in feedbacks:
            if information := re_match(pattern, feedback):
                if information.group(1) != current_note:
                    current_note = information.group(1)
                    print("")
                    print(f"Note: {current_note}")

                print(f"Date: {information.group(2)} {information.group(3)}")
                response = client_s3.access_s3_object(feedback)
                if response.status_code == HTTPStatus.OK.value:
                    print(wrapper.fill(response.content.decode("utf-8")))
                    print("")


if __name__ == "__main__":
    ReviewFeedbacks.run()
