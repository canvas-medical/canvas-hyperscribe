import json

from typing import NamedTuple


class NotionFeedbackRecord(NamedTuple):
    instance: str
    note_uuid: str
    date_time: str
    feedback: str

    def to_json(self, database_id: str) -> str:
        return json.dumps(
            {
                "parent": {"database_id": database_id},
                "properties": {
                    "Feedback Notion ID": {
                        "title": [
                            {"text": {"content": "."}}  # overwritten
                        ]
                    },
                    "Instance": {"rich_text": [{"text": {"content": self.instance}}]},
                    "Note UUID": {"rich_text": [{"text": {"content": self.note_uuid}}]},
                    "Date Time": {"rich_text": [{"text": {"content": self.date_time}}]},
                    "Feedback": {"rich_text": [{"text": {"content": self.feedback}}]},
                },
            }
        )
