import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch, call

from case_statistics import CaseStatistics
from evaluations.datastores.store_results import StoreResults


@patch.object(StoreResults, "_db_path")
def test_run(db_path, capsys):
    def reset_mocks():
        db_path.reset_mock()

    tested = CaseStatistics()
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)

        # no records
        tested.run()

        calls = [call()]
        assert db_path.mock_calls == calls
        exp_out = "\n".join([
            "------------------------------------------------------------------------------------------------------",
            "| case | run count | audio -> transcript | -> instructions | -> parameters | -> command | end to end |",
            "------------------------------------------------------------------------------------------------------",
            "------------------------------------------------------------------------------------------------------",
            "",
        ])
        assert capsys.readouterr().out == exp_out
        reset_mocks()

        # with records
        date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
        records = records = [
            # all pass with 4 tests
            {
                "now": date_0,
                "uuid": "uuid1",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
                "test": "audio2transcript",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            {
                "now": date_0,
                "uuid": "uuid1",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
                "test": "transcript2instructions",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            {
                "now": date_0,
                "uuid": "uuid1",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
                "test": "instruction2parameters",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            {
                "now": date_0,
                "uuid": "uuid1",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
                "test": "parameters2command",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            # all pass with 2 tests
            {
                "now": date_0,
                "uuid": "uuid2",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
                "test": "transcript2instructions",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            {
                "now": date_0,
                "uuid": "uuid2",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
                "test": "instruction2parameters",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            # one failed with 3 tests
            {
                "now": date_0,
                "uuid": "uuid3",
                "commit": "commit3",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase2",
                "test": "transcript2instructions",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            {
                "now": date_0,
                "uuid": "uuid3",
                "commit": "commit3",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase2",
                "test": "instruction2parameters",
                "duration": 1253.0,
                "passed": 0,
                "errors": "",
            },
            {
                "now": date_0,
                "uuid": "uuid3",
                "commit": "commit3",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase2",
                "test": "parameters2command",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
            # pass but unknown test
            {
                "now": date_0,
                "uuid": "uuid4",
                "commit": "commit3",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase3",
                "test": "theTest",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
        ]
        with sqlite3.connect(temp_file.name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(StoreResults._create_table_sql())
            for parameter in records:
                cursor.execute(StoreResults._insert_sql(), parameter)
            conn.commit()

        tested.run()

        calls = [call()]
        assert db_path.mock_calls == calls
        exp_out = "\n".join([
            "----------------------------------------------------------------------------------------------------------",
            "| case     | run count | audio -> transcript | -> instructions | -> parameters | -> command | end to end |",
            "----------------------------------------------------------------------------------------------------------",
            "| theCase1 |     2     |          1          |        2        |       2       |     1      |     2      |",
            "| theCase2 |     1     |                     |        1        |       0       |     1      |     0      |",
            "| theCase3 |     1     |                     |                 |               |            |     1      |",
            "----------------------------------------------------------------------------------------------------------",
            "",
        ])
        assert capsys.readouterr().out == exp_out
        reset_mocks()
