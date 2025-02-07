# from unittest.mock import patch, call
#
# from commander.protocols.temporary_data import TemporaryData
#
#
# @patch.object(TemporaryData, 'model_exists')
# def test_access_to_lab_data(model_exists):
#     def reset_mocks():
#         model_exists.reset_mock()
#
#     tested = TemporaryData
#     model_exists.side_effect = [False]
#     result = tested.access_to_lab_data()
#     assert result is False
#     calls = [call()]
#     assert model_exists.mock_calls == calls
#     reset_mocks()
