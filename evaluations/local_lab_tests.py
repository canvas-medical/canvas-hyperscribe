import sqlite3
from pathlib import Path

from hyperscribe.structures.coded_item import CodedItem

DATABASE = Path(__file__).parent / "generic_lab_tests.db"


def local_lab_tests(keywords: list[str]) -> list[CodedItem]:
    parameters = {f"kw_{idx:02d}": f"%{keyword}%" for idx, keyword in enumerate(keywords)}
    conditions = "".join(f" AND `keywords` LIKE :{name}" for name in parameters)
    sql = f"SELECT `order_code`, `order_name` FROM `generic_lab_test` WHERE 1=1{conditions} ORDER BY `dbid`"
    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, parameters).fetchall()
    return [CodedItem(uuid="", label=row["order_name"], code=row["order_code"]) for row in rows]
