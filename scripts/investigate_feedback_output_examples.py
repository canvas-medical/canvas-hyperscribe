"""
output: for each investigable claim, one or more observations that could lead to a hypothesis of what caused the issue. An observation is:
the claim id
a list of evidence items. An evidence item is:
transcript chunk id
"highlighted" transcript text and comment about its role in the claim
log chunk id
"highlighted log text and comment about its role in the claim
"""

output_example_1 = {
    "claim_id": 2,
    "claim_text": "the patient stopped taking their blood pressure meds but hyperscribe didn't record a stop command",
    "evidence_items": [
        {
            "transcript_evidence": [
                {
                    "chunk": 34,
                    "highlights": [{"patient": "yeah so I just thought maybe I should stop taking the medicine"}],
                    "investigator_comment": "There is no confirmation that the patient actually stopped taking their medicine, so this was placed in HPI instead of a stop command",
                }
            ],
            "log_evidence": None,
        }
    ],
}


output_example_2 = {
    "claim_id": 2,
    "claim_text": "the reason for visit was wrong",
    "evidence_items": [
        {
            "transcript_evidence": [
                {
                    "chunk": 2,
                    "highlights": [{"patient": "the main reason I'm here is just I'm so tired"}],
                    "investigator_comment": "The RFV should be fatigue, but is recorded as 'sick visted'",
                }
            ],
            "log_evidence": [
                {
                    "chunk": 2,
                    "highlights": [
                        "2025-09-23T20:03:38.605737+00:00: - ReasonForVisit #00 (11a9f6c4-e85b-412e-84a1-2b65f78fa5db, new/updated: False/False): Psychiatric Visit appointment with Dr. Carlene MacMillan.",
                        "2025-09-23T20:03:39.462712+00:00: status code: 403",
                    ],
                    "investigator_comment": "There was an authorization error just after the RFV command creation, whichj explains the failure to update RFV",
                }
            ],
        }
    ],
}
