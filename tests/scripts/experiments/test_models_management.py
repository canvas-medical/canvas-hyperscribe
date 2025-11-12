from argparse import Namespace
from unittest.mock import patch, call

from evaluations.structures.records.model import Model as ModelRecord
from scripts.experiments.models_management import ModelsManagement


@patch("scripts.experiments.models_management.ArgumentParser")
def test__parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = ModelsManagement

    argument_parser.return_value.parse_args.side_effect = [Namespace(vendor="theVendor")]

    result = tested._parameters()
    expected = Namespace(vendor="theVendor")
    assert result == expected

    calls = [
        call(description="Manage models in the database"),
        call().add_argument(
            "--vendor",
            type=str,
            required=True,
            help="The model vendor name",
        ),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("scripts.experiments.models_management.ModelStore")
@patch("scripts.experiments.models_management.HelperEvaluation")
@patch("scripts.experiments.models_management.getpass")
@patch.object(ModelsManagement, "_parameters")
def test_run(parameters, getpass_mock, helper, model_store, capsys):
    def reset_mocks():
        parameters.reset_mock()
        getpass_mock.reset_mock()
        helper.reset_mock()
        model_store.reset_mock()

    tested = ModelsManagement

    tests = [
        (
            "api-key",
            [
                ModelRecord(id=123, vendor="theVendor", api_key="other-api-key", model="theModel"),
                ModelRecord(id=147, vendor="theVendor", api_key="other-api-key", model=""),
            ],
            None,
            "model vendor 'theVendor' (model: theModel) updated\nmodel vendor 'theVendor' (model: default) updated\n",
            [
                call("thePostgresCredentials"),
                call().get_models_by_vendor("theVendor"),
                call().update_fields(123, {"api_key": "api-key"}),
                call().update_fields(147, {"api_key": "api-key"}),
            ],
        ),
        (
            "api-key",
            [ModelRecord(id=123, vendor="theVendor", api_key="api-key")],
            None,
            "no change made\n",
            [
                call("thePostgresCredentials"),
                call().get_models_by_vendor("theVendor"),
            ],
        ),
        (
            "api-key",
            [],
            ModelRecord(id=789, vendor="theVendor", api_key="api-key", model=""),
            "model vendor 'theVendor' added with id 789\n",
            [
                call("thePostgresCredentials"),
                call().get_models_by_vendor("theVendor"),
                call().insert(ModelRecord(vendor="theVendor", api_key="api-key", model="", id=0)),
            ],
        ),
    ]
    for api_key, get_model_result, insert_result, expected_output, calls_exp in tests:
        parameters.side_effect = [Namespace(vendor="theVendor")]
        getpass_mock.side_effect = [api_key]
        helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
        model_store.return_value.get_models_by_vendor.side_effect = [get_model_result]
        model_store.return_value.insert.side_effect = [insert_result]

        tested.run()

        assert capsys.readouterr().out == expected_output
        assert capsys.readouterr().err == ""

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [call("Enter the API key: ")]
        assert getpass_mock.mock_calls == calls
        calls = [call.postgres_credentials()]
        assert helper.mock_calls == calls
        assert model_store.mock_calls == calls_exp
        reset_mocks()
