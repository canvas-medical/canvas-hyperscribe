JSON_SCHEMAS: dict[str, dict] = {
    "audit": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "the referenced key"},
                "keyPath": {
                    "type": "string",
                    "description": "the JSON path of the referenced key from the root if there is more than one object",
                },
                "rationale": {"type": "string", "description": "the rationale of the provided value"},
            },
            "required": ["key", "rationale"],
            "additionalProperties": False,
        },
    },
    "audit_with_value": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "the referenced key"},
                    "value": {"description": "the provided value"},
                    "rationale": {"type": "string", "description": "the rationale of the provided value"},
                },
                "required": ["key", "value", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "command_custom_prompt": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "maxItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "newData": {
                    "type": "string",
                    "description": "the changed data as a single string of UTF-8 characters, "
                    "including \n for multiple lines",
                },
            },
            "required": ["newData"],
            "additionalProperties": False,
        },
    },
    "command_summary": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "maxItems": 1,
        "items": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        },
    },
    "template_enhanced_content": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "maxItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "enhancedContent": {
                    "type": "string",
                    "description": "the enhanced content incorporating template instructions",
                },
            },
            "required": ["enhancedContent"],
            "additionalProperties": False,
        },
    },
    "generic_parameters": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {"type": "object", "additionalProperties": True},
    },
    "prescription_dosage": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "quantityToDispense": {
                    "type": "number",
                    "exclusiveMinimum": 0.0,
                    "description": "the quantity to dispense",
                },
                "refills": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "the refills allowed",
                },
                "discreteQuantity": {
                    "type": "boolean",
                    "description": "whether the medication form is discrete "
                    "(e.g., tablets, capsules, patches, suppositories) as opposed to continuous "
                    "(e.g., milliliters, grams, ounces). Interpret the ncpdp quantity qualifier "
                    "description to determine this. Set to true for countable units, "
                    "false for measurable quantities.",
                },
                "noteToPharmacist": {
                    "type": "string",
                    "description": "the note to the pharmacist, as free text",
                },
                "informationToPatient": {
                    "type": "string",
                    "minLength": 1,
                    "description": "the information to the patient on how to use the medication, "
                    "specifying the quantity, the form (e.g. tablets, drops, puffs, etc), "
                    "the frequency and/or max daily frequency, and the route of use "
                    "(e.g. by mouth, applied to skin, dropped in eye, etc), as free text",
                },
            },
            "required": ["quantityToDispense", "refills", "discreteQuantity", "informationToPatient"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_concept": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "conceptId": {"type": "string", "minLength": 1},
                "term": {"type": "string", "minLength": 1},
            },
            "required": ["conceptId", "term"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_condition": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "ICD10": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
            },
            "required": ["ICD10", "label"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_contact": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "the index as provided in the list"},
                "contact": {"type": "string", "description": "the contact information as provided in the list"},
            },
            "required": ["index", "contact"],
            "additionalProperties": False,
        },
    },
    "selector_fdb_code": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "fdbCode": {"type": "integer", "minimum": 1},
                "description": {"type": "string", "minLength": 1},
            },
            "required": ["fdbCode", "description"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_immunization_codes": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "cptCode": {"type": "string", "minimum": 1},
                "cvxCode": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
            },
            "required": ["cptCode", "cvxCode", "label"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_lab_test": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
            },
            "required": ["code", "label"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_labels": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "labelId": {"type": "integer", "minimum": 1},
                "name": {"type": "string", "minLength": 1},
            },
            "required": ["labelId", "name"],
            "additionalProperties": False,
        },
        "minItems": 0,
    },
    "selector_assignee": {
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
    "voice_identification": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "speaker": {"type": "string", "minLength": 1},
                "voice": {"type": "string", "pattern": "^voice_[1-9]\\d*$"},
            },
            "required": ["speaker", "voice"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "uniqueItems": True,
    },
    "voice_split": {
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
    "voice_turns": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "speaker": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "start": {"type": "number", "default": 0.0},
                "end": {"type": "number", "default": 0.0},
            },
            "required": ["speaker", "text"],
            "additionalProperties": False,
        },
        "minItems": 1,
    },
}


class JsonSchema:
    @classmethod
    def get(cls, keys: list[str]) -> list[dict]:
        return [JSON_SCHEMAS[key] for key in keys if key in JSON_SCHEMAS]
