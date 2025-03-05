from hyperscribe.handlers.json_schema import JsonSchema


def test_get():
    tested = JsonSchema
    #
    result = tested.get([])
    assert result == []
    #
    result = tested.get(["selector_staff", "nope", "voice_split"])
    expected = [
        {
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
        {
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
    ]
    assert result == expected
