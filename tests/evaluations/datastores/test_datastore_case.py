from unittest.mock import patch, call

from evaluations.datastores.datastore_case import DatastoreCase
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.records.case import Case
from hyperscribe.structures.line import Line


@patch("evaluations.datastores.datastore_case.AuditorFile")
@patch("evaluations.datastores.datastore_case.PostgresCase")
@patch("evaluations.datastores.datastore_case.HelperEvaluation")
def test_already_generated(helper, psql_case, auditor_file):
    def reset_mock():
        helper.reset_mock()
        psql_case.reset_mock()
        auditor_file.reset_mock()

    tested = DatastoreCase

    exp_call_helper = [call.postgres_credentials(), call.postgres_credentials().is_ready()]
    # Postgres not ready
    for already_generated in [True, False]:
        helper.postgres_credentials.return_value.is_ready.side_effect = [False]
        psql_case.return_value.get_case.side_effect = []
        auditor_file.already_generated.side_effect = [already_generated]

        result = tested.already_generated("theCase")
        assert result is already_generated

        assert helper.mock_calls == exp_call_helper
        assert psql_case.mock_calls == []
        calls = [call.already_generated("theCase")]
        assert auditor_file.mock_calls == calls
        reset_mock()
    # Postgres is ready
    tests = [
        (
            Case(
                name="theCase",
                transcript={
                    "cycle_001": [Line(speaker="speaker1", text="text1"), Line(speaker="speaker2", text="text2")]
                },
                limited_chart={"limited": "chart"},
                profile="theProfile",
                validation_status=CaseStatus.GENERATION,
                batch_identifier="theBatchIdentifier",
                tags={"tag1": "theTag1", "tag2": "theTag2"},
                id=1456,
            ),
            True,
        ),
        (
            Case(
                name="theCase",
                transcript={},
                limited_chart={"limited": "chart"},
                profile="theProfile",
                validation_status=CaseStatus.GENERATION,
                batch_identifier="theBatchIdentifier",
                tags={"tag1": "theTag1", "tag2": "theTag2"},
                id=1456,
            ),
            False,
        ),  # empty transcript
        (
            Case(
                name="theCase",
                transcript={
                    "cycle_001": [Line(speaker="speaker1", text="text1"), Line(speaker="speaker2", text="text2")]
                },
                limited_chart={},
                profile="theProfile",
                validation_status=CaseStatus.GENERATION,
                batch_identifier="theBatchIdentifier",
                tags={"tag1": "theTag1", "tag2": "theTag2"},
                id=1456,
            ),
            False,
        ),  # empty limited chart
    ]
    for case, expected in tests:
        helper.postgres_credentials.return_value.is_ready.side_effect = [True]
        psql_case.return_value.get_case.side_effect = [case]
        auditor_file.already_generated.side_effect = [already_generated]

        result = tested.already_generated("theCase")
        assert result is expected

        assert helper.mock_calls == exp_call_helper
        calls = [
            call(helper.postgres_credentials.return_value),
            call().get_case("theCase"),
        ]
        assert psql_case.mock_calls == calls
        assert auditor_file.mock_calls == []
        reset_mock()


@patch("evaluations.datastores.datastore_case.AuditorFile")
@patch("evaluations.datastores.datastore_case.PostgresGeneratedNote")
@patch("evaluations.datastores.datastore_case.PostgresCase")
@patch("evaluations.datastores.datastore_case.HelperEvaluation")
def test_delete(helper, psql_case, psql_generated_note, auditor_file):
    def reset_mock():
        helper.reset_mock()
        psql_case.reset_mock()
        psql_generated_note.reset_mock()
        auditor_file.reset_mock()

    tested = DatastoreCase

    exp_call_helper = [call.postgres_credentials(), call.postgres_credentials().is_ready()]
    for audios in [False, True]:
        # Postgres not ready
        helper.postgres_credentials.return_value.is_ready.side_effect = [False]
        psql_case.return_value.get_id.side_effect = []

        tested.delete("theCase", audios)

        assert helper.mock_calls == exp_call_helper
        assert psql_case.mock_calls == []
        assert psql_generated_note.mock_calls == []
        calls = [call.reset("theCase", audios)]
        assert auditor_file.mock_calls == calls
        reset_mock()

        # Postgres is ready
        helper.postgres_credentials.return_value.is_ready.side_effect = [True]
        psql_case.return_value.get_id.side_effect = [45]

        tested.delete("theCase", audios)

        assert helper.mock_calls == exp_call_helper
        calls = [call(helper.postgres_credentials.return_value), call().get_id("theCase")]
        if audios:
            calls.extend([call(helper.postgres_credentials.return_value), call().update_fields(45, {"transcript": {}})])
        assert psql_case.mock_calls == calls
        calls = [call(helper.postgres_credentials.return_value), call().delete_for(45)]
        assert psql_generated_note.mock_calls == calls
        assert auditor_file.mock_calls == []
        reset_mock()


@patch("evaluations.datastores.datastore_case.FileSystemCase")
@patch("evaluations.datastores.datastore_case.PostgresCase")
@patch("evaluations.datastores.datastore_case.HelperEvaluation")
def test_all_names(helper, psql_case, fs_cases):
    def reset_mock():
        helper.reset_mock()
        psql_case.reset_mock()
        fs_cases.reset_mock()

    tested = DatastoreCase

    tests = [(True, ["name1", "name2"]), (False, ["name3", "name4"])]
    for psql_ready, expected in tests:
        helper.postgres_credentials.return_value.is_ready.side_effect = [psql_ready]
        psql_case.return_value.all_names.side_effect = [["name1", "name2"]]
        fs_cases.all.side_effect = [[EvaluationCase(case_name="name3"), EvaluationCase(case_name="name4")]]

        result = tested.all_names()
        assert result == expected

        calls = [call.postgres_credentials(), call.postgres_credentials().is_ready()]
        assert helper.mock_calls == calls
        calls = []
        if psql_ready:
            calls.extend([call(helper.postgres_credentials.return_value), call().all_names()])
        assert psql_case.mock_calls == calls
        calls = []
        if not psql_ready:
            calls.extend([call.all()])
        assert fs_cases.mock_calls == calls
        reset_mock()
