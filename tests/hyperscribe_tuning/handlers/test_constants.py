from hyperscribe_tuning.handlers.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "MAX_AUDIO_INTERVAL_SECONDS": '15',
        "MAX_AUTHENTICATION_TIME": 3600,
        "SECRET_API_SIGNING_KEY": "APISigningKey",
        "SECRET_AUDIO_INTERVAL_SECONDS": "AudioIntervalSeconds",
        "SECRET_AWS_KEY": "AwsKey",
        "SECRET_AWS_SECRET": "AwsSecret",
        "SECRET_AWS_REGION": "AwsRegion",
        "SECRET_AWS_BUCKET": "AwsBucket",
    }
    assert is_constant(tested, constants)
