from unittest.mock import patch, call

from case_list import CaseList
from evaluations.datastores.filesystem.case import Case as FileSystemCase
from evaluations.structures.evaluation_case import EvaluationCase


@patch.object(FileSystemCase, "all")
def test_run(mock_all, capsys):
    def reset_mocks():
        mock_all.reset_mock()

    tested = CaseList()
    # no records
    mock_all.side_effect = [[]]
    tested.run()

    calls = [call()]
    assert mock_all.mock_calls == calls
    exp_out = "\n".join([
        "------------------------------------------------------------------",
        "| environment | group | type | case | patient UUID | description |",
        "------------------------------------------------------------------",
        "------------------------------------------------------------------",
        "",
    ])
    assert capsys.readouterr().out == exp_out
    reset_mocks()

    # with records
    mock_all.side_effect = [
        [
            EvaluationCase(
                environment="theEnvironment1",
                patient_uuid="thePatientUuid1",
                case_type="theType1",
                case_group="theGroup1",
                case_name="theCaseName1",
                description="theDescription1",
            ),
            EvaluationCase(
                environment="theEnvironment2",
                patient_uuid="thePatientUuid2",
                case_type="theType2",
                case_group="theGroup2",
                case_name="theCaseName2",
                description="theDescription2",
            ),
            EvaluationCase(
                environment="theEnvironment3",
                patient_uuid="thePatientUuid3",
                case_type="theType3",
                case_group="theGroup3",
                case_name="theCaseName3",
                description="theDescription3",
            ),
        ]
    ]
    tested.run()

    calls = [call()]
    assert mock_all.mock_calls == calls
    exp_out = "\n".join([
        "---------------------------------------------------------------------------------------------",
        "| environment     | group     | type     | case         | patient UUID    | description     |",
        "---------------------------------------------------------------------------------------------",
        "| theEnvironment1 | theGroup1 | theType1 | theCaseName1 | thePatientUuid1 | theDescription1 |",
        "| theEnvironment2 | theGroup2 | theType2 | theCaseName2 | thePatientUuid2 | theDescription2 |",
        "| theEnvironment3 | theGroup3 | theType3 | theCaseName3 | thePatientUuid3 | theDescription3 |",
        "---------------------------------------------------------------------------------------------",
        "",
    ])
    assert capsys.readouterr().out == exp_out
    reset_mocks()
