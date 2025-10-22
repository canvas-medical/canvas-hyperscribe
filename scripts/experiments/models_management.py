from argparse import ArgumentParser, Namespace
from getpass import getpass

from evaluations.datastores.postgres.model import Model as ModelStore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.records.model import Model as ModelRecord


class ModelsManagement:
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Manage models in the database")
        parser.add_argument(
            "--vendor",
            type=str,
            required=True,
            help="The model vendor name",
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        args = cls._parameters()
        vendor: str = args.vendor

        api_key: str = getpass("Enter the API key: ")

        psql_credential = HelperEvaluation.postgres_credentials()
        model_store = ModelStore(psql_credential)

        model = model_store.get_model_by_vendor(vendor)

        message = "no change made"
        if model.id:
            if model.api_key != api_key:
                model_store.update_fields(model.id, {"api_key": api_key})
                message = f"model vendor '{vendor}' updated"
        else:
            model = model_store.insert(ModelRecord(vendor=vendor, api_key=api_key))
            message = f"model vendor '{vendor}' added with id {model.id}"
        print(message)


if __name__ == "__main__":
    ModelsManagement.run()
