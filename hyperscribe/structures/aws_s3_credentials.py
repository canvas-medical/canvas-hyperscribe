from __future__ import annotations

from typing import NamedTuple

from hyperscribe.libraries.constants import Constants


class AwsS3Credentials(NamedTuple):
    aws_key: str
    aws_secret: str
    region: str
    bucket: str

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> AwsS3Credentials:
        return AwsS3Credentials(
            aws_key=dictionary.get(Constants.SECRET_AWS_KEY, ""),
            aws_secret=dictionary.get(Constants.SECRET_AWS_SECRET, ""),
            region=dictionary.get(Constants.SECRET_AWS_REGION, ""),
            bucket=dictionary.get(Constants.SECRET_AWS_BUCKET_LOGS, ""),
        )

    @classmethod
    def from_dictionary_tuning(cls, dictionary: dict) -> AwsS3Credentials:
        return AwsS3Credentials(
            aws_key=dictionary.get(Constants.SECRET_AWS_KEY, ""),
            aws_secret=dictionary.get(Constants.SECRET_AWS_SECRET, ""),
            region=dictionary.get(Constants.SECRET_AWS_REGION, ""),
            bucket=dictionary.get(Constants.SECRET_AWS_BUCKET_TUNING, ""),
        )
