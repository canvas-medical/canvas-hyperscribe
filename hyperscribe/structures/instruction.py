from __future__ import annotations

from hyperscribe.libraries.helper_csv import HelperCsv


class Instruction:
    CSV_FIELDS = ["uuid", "index", "instruction", "information", "is_new", "is_updated"]

    def __init__(
        self,
        uuid: str,
        index: int,
        instruction: str,
        information: str,
        is_new: bool,
        is_updated: bool,
        previous_information: str,
    ):
        self.uuid = uuid
        self.index = index
        self.instruction = instruction
        self.information = information
        self.is_new = is_new
        self.is_updated = is_updated
        self.previous_information = previous_information

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Instruction]:
        return [
            Instruction(
                uuid=json_object.get("uuid", ""),
                index=json_object.get("index", 0),
                instruction=json_object.get("instruction", ""),
                information=json_object.get("information", ""),
                is_new=json_object.get("isNew", True),
                is_updated=json_object.get("isUpdated", False),
                previous_information="",
            )
            for json_object in json_list
        ]

    @classmethod
    def load_from_csv(cls, csv_list: list) -> list[Instruction]:
        if not csv_list:
            return []
        header = HelperCsv.parse_line(csv_list[0])
        field_indices = [header.index(f) for f in cls.CSV_FIELDS]
        results = []
        for csv_line in csv_list[1:]:
            cells = HelperCsv.parse_line(csv_line)
            values = [cells[i] for i in field_indices]
            vals: dict = {
                cls.CSV_FIELDS[0]: values[0],
                cls.CSV_FIELDS[1]: HelperCsv.int_value(values[1]),
                cls.CSV_FIELDS[2]: values[2],
                cls.CSV_FIELDS[3]: values[3],
                cls.CSV_FIELDS[4]: HelperCsv.bool_value(values[4]),
                cls.CSV_FIELDS[5]: HelperCsv.bool_value(values[5]),
                "previous_information": "",
            }
            results.append(cls(**vals))
        return results

    def to_json(self, reset_flags: bool) -> dict:
        return {
            "uuid": self.uuid,
            "index": self.index,
            "instruction": self.instruction,
            "information": self.information,
            "isNew": False if reset_flags else self.is_new,
            "isUpdated": False if reset_flags else self.is_updated,
        }

    def to_csv(self, reset_flags: bool) -> str:
        return ",".join(
            [
                HelperCsv.escape(self.uuid),
                HelperCsv.escape(self.index),
                HelperCsv.escape(self.instruction),
                HelperCsv.escape(self.information),
                HelperCsv.escape(False if reset_flags else self.is_new),
                HelperCsv.escape(False if reset_flags else self.is_updated),
            ]
        )

    def limited_str(self) -> str:
        return (
            f"{self.instruction} #{self.index:02d} "
            f"({self.uuid}, new/updated: {self.is_new}/{self.is_updated}): {self.information}"
        )

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Instruction)
        return (
            self.uuid == other.uuid
            and self.index == other.index
            and self.instruction == other.instruction
            and self.information == other.information
            and self.previous_information == other.previous_information
            and self.is_new == other.is_new
            and self.is_updated == other.is_updated
        )

    @classmethod
    def list_to_csv(cls, lines: list[Instruction]) -> str:
        result = [",".join(cls.CSV_FIELDS)]  # header row
        for line in lines:  # data rows
            row = [HelperCsv.escape(getattr(line, field)) for field in cls.CSV_FIELDS]
            result.append(",".join(row))
        return "\n".join(result)

    @classmethod
    def to_csv_description(cls, commands: list[str]) -> str:
        header = ",".join(cls.CSV_FIELDS)
        row = ",".join(
            [
                HelperCsv.escape(item)
                for item in [
                    "a unique identifier in this discussion",
                    "the 0-based appearance order of the instruction in this discussion",
                    f"one of: '{'/'.join(commands)}'",
                    "all relevant information extracted from the discussion explaining and/or defining the instruction",
                    "the instruction is new to the discussion",
                    "the instruction is an update of an instruction previously identified in the discussion",
                ]
            ]
        )
        return "\n".join([header, row])
