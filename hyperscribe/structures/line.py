from __future__ import annotations

from typing import NamedTuple

from hyperscribe.libraries.helper_csv import HelperCsv


class Line(NamedTuple):
    speaker: str
    text: str
    start: float = 0.0
    end: float = 0.0

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Line]:
        return [
            Line(
                speaker=json_object.get("speaker", ""),
                text=json_object.get("text", ""),
                start=json_object.get("start") or 0.0,
                end=json_object.get("end") or 0.0,
            )
            for json_object in json_list
        ]

    @classmethod
    def load_from_csv(cls, csv_list: list) -> list[Line]:
        if not csv_list:
            return []
        header = HelperCsv.parse_line(csv_list[0])
        field_indices = [header.index(f) for f in cls._fields]
        results = []
        for csv_line in csv_list[1:]:
            cells = HelperCsv.parse_line(csv_line)
            values = [cells[i] for i in field_indices]
            vals: dict = {
                cls._fields[0]: values[0],
                cls._fields[1]: values[1],
                cls._fields[2]: HelperCsv.float_value(values[2]),
                cls._fields[3]: HelperCsv.float_value(values[3]),
            }
            results.append(cls(**vals))
        return results

    def to_json(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def tail_of(cls, exchange: list[Line], max_words: int) -> list[Line]:
        result: list[Line] = []
        for line in exchange[::-1]:
            words_count = sum([len(l.text.split()) for l in result])
            next_count = len(line.text.split())
            if words_count + next_count < max_words:
                result.insert(0, line)
            else:
                result.insert(
                    0,
                    Line(
                        speaker=line.speaker,
                        text=" ".join(line.text.split()[-1 * (max_words - words_count) :]),
                        start=line.start,  # <-- not accurate but good enough
                        end=line.end,
                    ),
                )
                break
        return result

    @classmethod
    def list_to_csv(cls, lines: list[Line]) -> str:
        result = [",".join(cls._fields)]  # header row
        for line in lines:  # data rows
            row = [HelperCsv.escape(getattr(line, field)) for field in cls._fields]
            result.append(",".join(row))
        return "\n".join(result)

    @classmethod
    def to_csv_description(cls) -> str:
        header = ",".join(cls._fields)
        row = ",".join(
            [
                HelperCsv.escape(item)
                for item in [
                    "Patient/Clinician/Nurse/Parent...",
                    "the verbatim transcription as reported in the transcription",
                    "the start as reported in the transcription",
                    "the end as reported in the transcription",
                ]
            ]
        )
        return "\n".join([header, row])
