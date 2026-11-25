from html import escape
from typing import NamedTuple


class PylonFeedbackRecord(NamedTuple):
    instance: str
    note_uuid: str
    date_time: str
    feedback: str
    requester_email: str | None

    def to_issue_params(self) -> dict:
        return {
            "title": f"Hyperscribe Feedback - {self.instance} - {self.date_time}",
            "body_html": (
                f"<p>{escape(self.feedback)}</p>"
                f"<p><b>Instance:</b> {self.instance}<br>"
                f"<b>Note:</b> {self.note_uuid}<br>"
                f"<b>Date:</b> {self.date_time}</p>"
            ),
        }
