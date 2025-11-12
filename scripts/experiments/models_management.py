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

        models = model_store.get_models_by_vendor(vendor)

        messages: list = []
        if models:
            for model in models:
                if model.api_key != api_key:
                    model_store.update_fields(model.id, {"api_key": api_key})
                    messages.append(f"model vendor '{vendor}' (model: {model.model or 'default'}) updated")
        else:
            model = model_store.insert(ModelRecord(vendor=vendor, api_key=api_key, model=""))
            messages.append(f"model vendor '{vendor}' added with id {model.id}")
        if not messages:
            messages.append("no change made")
        for message in messages:
            print(message)


if __name__ == "__main__":
    ModelsManagement.run()
