import re
from typing import Any


class HelperCsv:
    # (?:^|,)              # start of line or comma
    # (?:                  # start group for quoted or unquoted fields
    #   "((?:[^"]|"")*)"   # quoted field: double quotes escaped as ""
    # |                    # ...or...
    #   ([^",]*)           # unquoted field: anything except comma or quote
    # )
    PATTERN_VALUE = re.compile(r'(?:^|,)(?:"((?:[^"]|"")*)"|([^",]*))')

    @classmethod
    def escape(cls, string: Any) -> str:
        string = str(string).replace('"', '""')  # Escape double quotes by doubling them
        if any(c in string for c in [",", '"', "\n"]):  # Quote value if it contains comma, quote, or newline
            return f'"{string}"'
        return str(string)

    @classmethod
    def parse_line(cls, line: str) -> list[str]:
        result = []
        for match in cls.PATTERN_VALUE.finditer(line):
            quoted, unquoted = match.groups()
            if quoted is not None:
                # replace double-quote escape
                result.append(quoted.replace('""', '"'))
            else:
                result.append(unquoted)
        return result

    @classmethod
    def int_value(cls, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return 0

    @classmethod
    def float_value(cls, value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return 0.0

    @classmethod
    def bool_value(cls, value: str) -> bool:
        if value.lower() in ["true", "t", "yes", "y", "1"]:
            return True
        return False
