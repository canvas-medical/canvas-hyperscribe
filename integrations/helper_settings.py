from os import environ

from commander.protocols.commander import Commander
from commander.protocols.structures.settings import Settings


class HelperSettings:
    @classmethod
    def settings(cls) -> Settings:
        return Settings(
            openai_key=environ[Commander.SECRET_OPENAI_KEY],
            science_host=environ[Commander.SECRET_SCIENCE_HOST],
            ontologies_host=environ[Commander.SECRET_ONTOLOGIES_HOST],
            pre_shared_key=environ[Commander.SECRET_PRE_SHARED_KEY],
            allow_update=True,
        )
