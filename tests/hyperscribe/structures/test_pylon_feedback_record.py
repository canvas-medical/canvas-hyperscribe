from hyperscribe.structures.pylon_feedback_record import PylonFeedbackRecord


def test_to_issue_params():
    record = PylonFeedbackRecord(
        instance="test-instance",
        note_uuid="note-123",
        date_time="20250829-101457",
        feedback="The transcription missed a medication.",
        requester_email="doctor@example.com",
    )
    result = record.to_issue_params()
    assert result == {
        "title": "Hyperscribe Feedback - test-instance - 20250829-101457",
        "body_html": (
            "<p>The transcription missed a medication.</p>"
            "<p><b>Instance:</b> test-instance<br>"
            "<b>Note:</b> note-123<br>"
            "<b>Date:</b> 20250829-101457</p>"
        ),
    }


def test_to_issue_params_html_escaping():
    record = PylonFeedbackRecord(
        instance="test-instance",
        note_uuid="note-123",
        date_time="20250829-101457",
        feedback='<script>alert("xss")</script>',
        requester_email=None,
    )
    result = record.to_issue_params()
    assert "&lt;script&gt;" in result["body_html"]
    assert "<script>" not in result["body_html"]
