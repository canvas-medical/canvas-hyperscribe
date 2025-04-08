JSON_SCHEMAS = {
    "audit": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "the referenced key",
                },
                "keyPath": {
                    "type": "string",
                    "description": "the JSON path of the referenced key from the root if there is more than one object",
                },
                "rational": {
                    "type": "string",
                    "description": "the rational of the provided value",
                },
            },
            "required": ["key", "rational"],
            "additionalProperties": False,
        }
    },
    "generic_parameters": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": True,
        }
    },
    "prescription_dosage": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "quantityToDispense": {"type": "number", "exclusiveMinimum": 0},
                "refills": {"type": "integer", "minimum": 0},
                "noteToPharmacist": {"type": "string"},
                "informationToPatient": {"type": "string", "minLength": 1},
            },
            "required": ["quantityToDispense", "refills", "informationToPatient"],
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
                "index": {
                    "type": "integer",
                    "description": "the index as provided in the list",
                },
                "contact": {
                    "type": "string",
                    "description": "the contact information as provided in the list",
                },
            },
            "required": ["index", "contact"],
            "additionalProperties": False,
        }
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
    "selector_label": {
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
        "minItems": 1,
        "maxItems": 1,
    },
    "selector_staff": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "staffId": {"type": "integer", "minimum": 1},
                "name": {"type": "string", "minLength": 1},
            },
            "required": ["staffId", "name"],
            "additionalProperties": False,
        },
        "minItems": 1,
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
            },
            "required": ["voice", "text"],
            "additionalProperties": False,
        },
        "minItems": 1,
    },
}


class JsonSchema:

    @classmethod
    def get(cls, keys: list[str]) -> list[dict]:
        return [JSON_SCHEMAS[key] for key in keys if key in JSON_SCHEMAS]
