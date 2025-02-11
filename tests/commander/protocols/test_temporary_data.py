from unittest.mock import patch, call

from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from commander.protocols.temporary_data import TemporaryData, DataLabView, DataLabTestView


_ = LabOrderCommand # <--- just to force the Django Settings

@patch.object(TemporaryData, 'model_exists')
def test_access_to_lab_data(model_exists):
    def reset_mocks():
        model_exists.reset_mock()

    tested = TemporaryData

    model_exists.side_effect = [False]
    result = tested.access_to_lab_data()
    assert result is False
    calls = [call(DataLabView)]
    assert model_exists.mock_calls == calls
    reset_mocks()

    model_exists.side_effect = [True, False]
    result = tested.access_to_lab_data()
    assert result is False
    calls = [
        call(DataLabView),
        call(DataLabTestView),
    ]
    assert model_exists.mock_calls == calls
    reset_mocks()

    model_exists.side_effect = [True, True]
    result = tested.access_to_lab_data()
    assert result is True
    calls = [
        call(DataLabView),
        call(DataLabTestView),
    ]
    assert model_exists.mock_calls == calls
    reset_mocks()

@patch.object(DataLabTestView, 'objects')
def test_model_exists(model_db):
    def reset_mocks():
        model_db.reset_mock()

    tested = TemporaryData
    model_db.count.side_effect = [3]
    result = tested.model_exists(DataLabTestView)
    assert result is True
    calls = [call.count()]
    assert model_db.mock_calls == calls
    reset_mocks()

    model_db.count.side_effect = [Exception("TestIssue")]
    result = tested.model_exists(DataLabTestView)
    assert result is False
    calls = [call.count()]
    assert model_db.mock_calls == calls
    reset_mocks()
