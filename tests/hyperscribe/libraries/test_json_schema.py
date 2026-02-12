from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase


def test_schema_audit():
    schema = JsonSchema.get(["audit"])[0]
    tests = [
        ([], ""),
        ([{"key": "theKey", "rationale": "theRationale"}], ""),
        (
            [{"key": "theKey", "rationale": "theRationale", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"key": "theKey"}],
            "'rationale' is a required property, in path [0]",
        ),
        (
            [{"rationale": "theRationale"}],
            "'key' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_audit_with_value():
    schema = JsonSchema.get(["audit_with_value"])[0]
    tests = [
        ([], ""),
        ([[{"key": "theKey", "value": "theValue", "rationale": "theRationale"}]], ""),
        (
            [[{"key": "theKey", "value": "theValue", "rationale": "theRationale", "other": "added"}]],
            "Additional properties are not allowed ('other' was unexpected), in path [0, 0]",
        ),
        (
            [[{"key": "theKey", "value": "theValue"}]],
            "'rationale' is a required property, in path [0, 0]",
        ),
        (
            [[{"key": "theKey", "rationale": "theRationale"}]],
            "'value' is a required property, in path [0, 0]",
        ),
        (
            [[{"value": "theValue", "rationale": "theRationale"}]],
            "'key' is a required property, in path [0, 0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_command_custom_prompt():
    schema = JsonSchema.get(["command_custom_prompt"])[0]
    tests = [
        ([{"newData": "theData"}], ""),
        ([{"newData": "line1\nline2"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"newData": "data1"}, {"newData": "data2"}],
            "[{'newData': 'data1'}, {'newData': 'data2'}] is too long",
        ),
        (
            [{"newData": "theData", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{}],
            "'newData' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_command_summary():
    schema = JsonSchema.get(["command_summary"])[0]
    tests = [
        ([{"summary": "theSummary"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"summary": "summary1"}, {"summary": "summary2"}],
            "[{'summary': 'summary1'}, {'summary': 'summary2'}] is too long",
        ),
        (
            [{"summary": "theSummary", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{}],
            "'summary' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_generic_parameters():
    schema = JsonSchema.get(["generic_parameters"])[0]
    tests = [
        ([], ""),
        ([{}], ""),
        ([{"key": "value"}], ""),
        ([{"key": "value", "other": "allowed"}], ""),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_prescription_dosage():
    schema = JsonSchema.get(["prescription_dosage"])[0]
    tests = [
        (
            [
                {
                    "quantityToDispense": 10.5,
                    "refills": 2,
                    "discreteQuantity": True,
                    "informationToPatient": "Take daily",
                }
            ],
            "",
        ),
        (
            [
                {
                    "quantityToDispense": 10.5,
                    "refills": 2,
                    "discreteQuantity": False,
                    "noteToPharmacist": "Note",
                    "informationToPatient": "Take daily",
                }
            ],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {
                    "quantityToDispense": 10,
                    "refills": 2,
                    "discreteQuantity": True,
                    "informationToPatient": "Daily",
                },
                {
                    "quantityToDispense": 5,
                    "refills": 1,
                    "discreteQuantity": False,
                    "informationToPatient": "Nightly",
                },
            ],
            "[{'quantityToDispense': 10, 'refills': 2, 'discreteQuantity': True, 'informationToPatient': 'Daily'}, "
            "{'quantityToDispense': 5, 'refills': 1, 'discreteQuantity': False, 'informationToPatient': 'Nightly'}] "
            "is too long",
        ),
        (
            [
                {
                    "quantityToDispense": 10,
                    "refills": 2,
                    "discreteQuantity": True,
                    "informationToPatient": "Take daily",
                    "other": "added",
                }
            ],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"quantityToDispense": 0, "refills": 2, "discreteQuantity": True, "informationToPatient": "Take daily"}],
            "0 is less than or equal to the minimum of 0.0, in path [0, 'quantityToDispense']",
        ),
        (
            [{"quantityToDispense": -5, "refills": 2, "discreteQuantity": True, "informationToPatient": "Take daily"}],
            "-5 is less than or equal to the minimum of 0.0, in path [0, 'quantityToDispense']",
        ),
        (
            [{"quantityToDispense": 10, "refills": -1, "discreteQuantity": True, "informationToPatient": "Take daily"}],
            "-1 is less than the minimum of 0, in path [0, 'refills']",
        ),
        (
            [{"quantityToDispense": 10, "refills": 2, "discreteQuantity": True, "informationToPatient": ""}],
            "'' should be non-empty, in path [0, 'informationToPatient']",
        ),
        (
            [{"refills": 2, "discreteQuantity": True, "informationToPatient": "Take daily"}],
            "'quantityToDispense' is a required property, in path [0]",
        ),
        (
            [{"quantityToDispense": 10, "discreteQuantity": True, "informationToPatient": "Take daily"}],
            "'refills' is a required property, in path [0]",
        ),
        (
            [{"quantityToDispense": 10, "refills": 2, "informationToPatient": "Take daily"}],
            "'discreteQuantity' is a required property, in path [0]",
        ),
        (
            [{"quantityToDispense": 10, "refills": 2, "discreteQuantity": True}],
            "'informationToPatient' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_concept():
    schema = JsonSchema.get(["selector_concept"])[0]
    tests = [
        ([{"conceptId": "123", "term": "theTerm"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"conceptId": "123", "term": "term1"}, {"conceptId": "456", "term": "term2"}],
            "[{'conceptId': '123', 'term': 'term1'}, {'conceptId': '456', 'term': 'term2'}] is too long",
        ),
        (
            [{"conceptId": "123", "term": "theTerm", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"conceptId": "", "term": "theTerm"}],
            "'' should be non-empty, in path [0, 'conceptId']",
        ),
        (
            [{"conceptId": "123", "term": ""}],
            "'' should be non-empty, in path [0, 'term']",
        ),
        (
            [{"term": "theTerm"}],
            "'conceptId' is a required property, in path [0]",
        ),
        (
            [{"conceptId": "123"}],
            "'term' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_condition():
    schema = JsonSchema.get(["selector_condition"])[0]
    tests = [
        ([{"ICD10": "A01.2", "label": "theLabel"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"ICD10": "A01", "label": "label1"}, {"ICD10": "B02", "label": "label2"}],
            "[{'ICD10': 'A01', 'label': 'label1'}, {'ICD10': 'B02', 'label': 'label2'}] is too long",
        ),
        (
            [{"ICD10": "A01", "label": "theLabel", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"ICD10": "", "label": "theLabel"}],
            "'' should be non-empty, in path [0, 'ICD10']",
        ),
        (
            [{"ICD10": "A01", "label": ""}],
            "'' should be non-empty, in path [0, 'label']",
        ),
        (
            [{"label": "theLabel"}],
            "'ICD10' is a required property, in path [0]",
        ),
        (
            [{"ICD10": "A01"}],
            "'label' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_contact():
    schema = JsonSchema.get(["selector_contact"])[0]
    tests = [
        ([], ""),
        ([{"index": 1, "contact": "theContact"}], ""),
        (
            [{"index": 1, "contact": "theContact", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"contact": "theContact"}],
            "'index' is a required property, in path [0]",
        ),
        (
            [{"index": 1}],
            "'contact' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_fdb_code():
    schema = JsonSchema.get(["selector_fdb_code"])[0]
    tests = [
        ([{"fdbCode": 123, "description": "theDescription"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"fdbCode": 123, "description": "desc1"}, {"fdbCode": 456, "description": "desc2"}],
            "[{'fdbCode': 123, 'description': 'desc1'}, {'fdbCode': 456, 'description': 'desc2'}] is too long",
        ),
        (
            [{"fdbCode": 123, "description": "theDescription", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"fdbCode": 0, "description": "theDescription"}],
            "0 is less than the minimum of 1, in path [0, 'fdbCode']",
        ),
        (
            [{"fdbCode": 123, "description": ""}],
            "'' should be non-empty, in path [0, 'description']",
        ),
        (
            [{"description": "theDescription"}],
            "'fdbCode' is a required property, in path [0]",
        ),
        (
            [{"fdbCode": 123}],
            "'description' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_immunization_codes():
    schema = JsonSchema.get(["selector_immunization_codes"])[0]
    tests = [
        ([{"cptCode": "90471", "cvxCode": "03", "label": "theLabel"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {"cptCode": "90471", "cvxCode": "03", "label": "label1"},
                {"cptCode": "90472", "cvxCode": "04", "label": "label2"},
            ],
            "[{'cptCode': '90471', 'cvxCode': '03', 'label': 'label1'}, "
            "{'cptCode': '90472', 'cvxCode': '04', 'label': 'label2'}] is too long",
        ),
        (
            [{"cptCode": "90471", "cvxCode": "03", "label": "theLabel", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"cptCode": "90471", "cvxCode": "", "label": "theLabel"}],
            "'' should be non-empty, in path [0, 'cvxCode']",
        ),
        (
            [{"cptCode": "90471", "cvxCode": "03", "label": ""}],
            "'' should be non-empty, in path [0, 'label']",
        ),
        (
            [{"cvxCode": "03", "label": "theLabel"}],
            "'cptCode' is a required property, in path [0]",
        ),
        (
            [{"cptCode": "90471", "label": "theLabel"}],
            "'cvxCode' is a required property, in path [0]",
        ),
        (
            [{"cptCode": "90471", "cvxCode": "03"}],
            "'label' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_lab_test():
    schema = JsonSchema.get(["selector_lab_test"])[0]
    tests = [
        ([{"code": "12345", "label": "theLabel"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"code": "12345", "label": "label1"}, {"code": "67890", "label": "label2"}],
            "[{'code': '12345', 'label': 'label1'}, {'code': '67890', 'label': 'label2'}] is too long",
        ),
        (
            [{"code": "12345", "label": "theLabel", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"code": "", "label": "theLabel"}],
            "'' should be non-empty, in path [0, 'code']",
        ),
        (
            [{"code": "12345", "label": ""}],
            "'' should be non-empty, in path [0, 'label']",
        ),
        (
            [{"label": "theLabel"}],
            "'code' is a required property, in path [0]",
        ),
        (
            [{"code": "12345"}],
            "'label' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_labels():
    schema = JsonSchema.get(["selector_labels"])[0]
    tests = [
        ([], ""),
        ([{"labelId": 1, "name": "theName"}], ""),
        (
            [{"labelId": 1, "name": "name1"}, {"labelId": 2, "name": "name2"}],
            "",
        ),
        (
            [{"labelId": 1, "name": "theName", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"labelId": 0, "name": "theName"}],
            "0 is less than the minimum of 1, in path [0, 'labelId']",
        ),
        (
            [{"labelId": 1, "name": ""}],
            "'' should be non-empty, in path [0, 'name']",
        ),
        (
            [{"name": "theName"}],
            "'labelId' is a required property, in path [0]",
        ),
        (
            [{"labelId": 1}],
            "'name' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_selector_assignee():
    schema = JsonSchema.get(["selector_assignee"])[0]
    tests = [
        ([{"type": "staff", "id": 1, "name": "theName"}], ""),
        ([{"type": "team", "id": 2, "name": "theName"}], ""),
        ([{"type": "role", "id": 3, "name": "theName"}], ""),
        ([], ""),
        (
            [{"type": "staff", "id": 1, "name": "name1"}, {"type": "team", "id": 2, "name": "name2"}],
            "[{'type': 'staff', 'id': 1, 'name': 'name1'}, {'type': 'team', 'id': 2, 'name': 'name2'}] is too long",
        ),
        (
            [{"type": "staff", "id": 1, "name": "theName", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"type": "invalid", "id": 1, "name": "theName"}],
            "'invalid' is not one of ['staff', 'team', 'role'], in path [0, 'type']",
        ),
        (
            [{"type": "staff", "id": 0, "name": "theName"}],
            "0 is less than the minimum of 1, in path [0, 'id']",
        ),
        (
            [{"type": "staff", "id": 1, "name": ""}],
            "'' should be non-empty, in path [0, 'name']",
        ),
        (
            [{"id": 1, "name": "theName"}],
            "'type' is a required property, in path [0]",
        ),
        (
            [{"type": "staff", "name": "theName"}],
            "'id' is a required property, in path [0]",
        ),
        (
            [{"type": "staff", "id": 1}],
            "'name' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_voice_identification():
    schema = JsonSchema.get(["voice_identification"])[0]
    tests = [
        ([{"speaker": "Doctor", "voice": "voice_1"}], ""),
        ([{"speaker": "Doctor", "voice": "voice_1"}, {"speaker": "Patient", "voice": "voice_2"}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"speaker": "Doctor", "voice": "voice_1", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"speaker": "", "voice": "voice_1"}],
            "'' should be non-empty, in path [0, 'speaker']",
        ),
        (
            [{"speaker": "Doctor", "voice": "voice_0"}],
            "'voice_0' does not match '^voice_[1-9]\\\\d*$', in path [0, 'voice']",
        ),
        (
            [{"speaker": "Doctor", "voice": "invalid"}],
            "'invalid' does not match '^voice_[1-9]\\\\d*$', in path [0, 'voice']",
        ),
        (
            [{"voice": "voice_1"}],
            "'speaker' is a required property, in path [0]",
        ),
        (
            [{"speaker": "Doctor"}],
            "'voice' is a required property, in path [0]",
        ),
        (
            [{"speaker": "Doctor", "voice": "voice_1"}, {"speaker": "Doctor", "voice": "voice_1"}],
            "[{'speaker': 'Doctor', 'voice': 'voice_1'}, "
            "{'speaker': 'Doctor', 'voice': 'voice_1'}] has non-unique elements",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_voice_split():
    schema = JsonSchema.get(["voice_split"])[0]
    tests = [
        ([{"voice": "voice_1", "text": "Hello"}], ""),
        ([{"voice": "voice_1", "text": "Hello", "start": 0.0, "end": 1.5}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"voice": "voice_1", "text": "Hello", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"voice": "voice_0", "text": "Hello"}],
            "'voice_0' does not match '^voice_[1-9]\\\\d*$', in path [0, 'voice']",
        ),
        (
            [{"voice": "voice_1", "text": ""}],
            "'' should be non-empty, in path [0, 'text']",
        ),
        (
            [{"text": "Hello"}],
            "'voice' is a required property, in path [0]",
        ),
        (
            [{"voice": "voice_1"}],
            "'text' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_schema_voice_turns():
    schema = JsonSchema.get(["voice_turns"])[0]
    tests = [
        ([{"speaker": "Doctor", "text": "Hello"}], ""),
        ([{"speaker": "Doctor", "text": "Hello", "start": 0.0, "end": 1.5}], ""),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [{"speaker": "Doctor", "text": "Hello", "other": "added"}],
            "Additional properties are not allowed ('other' was unexpected), in path [0]",
        ),
        (
            [{"speaker": "", "text": "Hello"}],
            "'' should be non-empty, in path [0, 'speaker']",
        ),
        (
            [{"speaker": "Doctor", "text": ""}],
            "'' should be non-empty, in path [0, 'text']",
        ),
        (
            [{"text": "Hello"}],
            "'speaker' is a required property, in path [0]",
        ),
        (
            [{"speaker": "Doctor"}],
            "'text' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_get():
    tested = JsonSchema
    #
    result = tested.get([])
    assert result == []
    #
    result = tested.get(["selector_assignee", "nope", "voice_split"])
    expected = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["staff", "team", "role"]},
                    "id": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "minLength": 1},
                },
                "required": ["type", "id", "name"],
                "additionalProperties": False,
            },
            "minItems": 0,
            "maxItems": 1,
        },
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "voice": {"type": "string", "pattern": "^voice_[1-9]\\d*$"},
                    "text": {"type": "string", "minLength": 1},
                    "start": {"type": "number", "default": 0.0},
                    "end": {"type": "number", "default": 0.0},
                },
                "required": ["voice", "text"],
                "additionalProperties": False,
            },
            "minItems": 1,
        },
    ]
    assert result == expected
