import json
from datetime import timezone, datetime
from unittest.mock import MagicMock, patch, call

from hyperscribe.libraries.cached_discussion import CachedDiscussion
from hyperscribe.libraries.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


@patch('hyperscribe.libraries.llm_decisions_reviewer.MemoryLog')
@patch('hyperscribe.libraries.llm_decisions_reviewer.LlmTurnsStore')
@patch('hyperscribe.libraries.llm_decisions_reviewer.Helper')
@patch('hyperscribe.libraries.llm_decisions_reviewer.CachedDiscussion')
@patch('hyperscribe.libraries.llm_decisions_reviewer.AwsS3')
def test_review(
        aws_s3,
        cached_discussion,
        helper,
        llm_turns_store,
        memory_log,
):
    mock_memory_log = MagicMock()

    def reset_mocks():
        aws_s3.reset_mock()
        cached_discussion.reset_mock()
        helper.reset_mock()
        llm_turns_store.reset_mock()
        memory_log.reset_mock()
        mock_memory_log.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    aws_s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )

    llm_turns_store.indexed_instruction = LlmTurnsStore.indexed_instruction
    llm_turns_store.decompose = LlmTurnsStore.decompose

    expected_uploads = [
        [
            {
                "uuid": "transcript2instructions_00",
                "command": "transcript2instructions",
                "increment": 0,
                "decision": ["model_t2i_00"],
                "audit": "audit01A",
            },
            {
                "uuid": "transcript2instructions_01",
                "command": "transcript2instructions",
                "increment": 1,
                "decision": ["model_t2i_01"],
                "audit": "audit01B",
            },
            {
                "uuid": "uuid1",
                "command": "canvasCommandX_00",
                "increment": 0,
                "decision": ["model_00_00"],
                "audit": "audit02",
            },
            {
                "uuid": "uuid1",
                "command": "canvasCommandX_00",
                "increment": 1,
                "decision": ["model_00_01"],
                "audit": "audit03",
            },
        ],
        [
            {
                "uuid": "uuid2",
                "command": "canvasCommandY_01",
                "increment": 0,
                "decision": ["model_01_00"],
                "audit": "audit04",
            },
            {
                "uuid": "uuid3",
                "command": "canvasCommandY_02",
                "increment": 0,
                "decision": ["model_02_00"],
                "audit": "audit05",
            },
        ],
        [],
        [
            {
                "uuid": "uuid4",
                "command": "Questionnaire_06",
                "increment": 0,
                "decision": ["model_06_00"],
                "audit": "audit06",
            },
        ],
    ]
    schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'key': {'type': 'string', 'description': 'the referenced key'},
                    'value': {'description': 'the provided value'},
                    'rationale': {'type': 'string', 'description': 'the rationale of the provided value'},
                },
                'required': ['key', 'value', 'rationale'],
                'additionalProperties': False,
            },
        },
    }
    exp_system_prompts = {
        "transcript1": [
            'Your task is now to explain the rationale of each and every value you have provided, citing any text or value you used.',
            'Mention specific parts of the transcript to support the rationale.',
            'Present the reasoning behind each and every value you provided, your response should be a JSON following this JSON Schema:',
            '```json',
            json.dumps(schema),
            '```',
            '',
        ],
        "transcript2": [
            'Your task is now to explain the rationale of each and every value you have provided, citing any text or value you used.',
            'Mention specific parts of the transcript to support the rationale.\nReport only the items with changed value between your last response and the ones you provided before.',
            'Present the reasoning behind each and every value you provided, your response should be a JSON following this JSON Schema:',
            '```json',
            json.dumps(schema),
            '```',
            '',
        ],
        "common": [
            'Your task is now to explain the rationale of each and every value you have provided, citing any text or value you used.',
            '',
            'Present the reasoning behind each and every value you provided, your response should be a JSON following this JSON Schema:',
            '```json',
            json.dumps(schema),
            '```',
            '',
        ],
        "questionnaire": [
            'Your task is now to explain the rationale of each and every value you have provided, citing any text or value you used.',
            'Report only the items with changed value and mention specific parts of the transcript to support the rationale.',
            'Present the reasoning behind each and every value you provided, your response should be a JSON following this JSON Schema:',
            '```json',
            json.dumps(schema),
            '```',
            '',
        ],
    }
    command2uuid = {
        "canvasCommandX_00": "uuid1",
        "canvasCommandY_01": "uuid2",
        "canvasCommandY_02": "uuid3",
        "Questionnaire_06": "uuid4",
    }
    date_x = datetime(2025, 5, 7, 12, 40, 21, tzinfo=timezone.utc)
    tested = LlmDecisionsReviewer

    # no audit
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=False,
    )
    aws_s3.return_value.is_ready.side_effect = []
    cached_discussion.get_discussion.side_effect = []
    llm_turns_store.return_value.stored_document.side_effect = []
    helper.chatter.return_value.single_conversation.side_effect = []
    memory_log.instance.side_effect = []

    tested.review(identification, settings, aws_s3_credentials, mock_memory_log, command2uuid, date_x, 5)

    assert aws_s3.mock_calls == []
    assert cached_discussion.mock_calls == []
    assert helper.mock_calls == []
    assert llm_turns_store.mock_calls == []
    assert mock_memory_log.mock_calls == []
    reset_mocks()

    # with audit
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=True,
    )
    # -- S3 not ready
    aws_s3.return_value.is_ready.side_effect = [False]
    cached_discussion.get_discussion.side_effect = [CachedDiscussion("noteUuid")]
    llm_turns_store.return_value.stored_document.side_effect = []
    helper.chatter.return_value.single_conversation.side_effect = []
    memory_log.instance.side_effect = []

    tested.review(identification, settings, aws_s3_credentials, mock_memory_log, command2uuid, date_x, 5)
    calls = [
        call(aws_s3_credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    assert cached_discussion.mock_calls == []
    assert helper.mock_calls == []
    assert llm_turns_store.mock_calls == []
    assert mock_memory_log.mock_calls == []
    reset_mocks()

    # -- S3 ready + documents
    aws_s3.return_value.is_ready.side_effect = [True]
    llm_turns_store.return_value.stored_documents.side_effect = [
        [
            ("transcript2instructions_00", [
                {"role": "system", "text": ["system_t2i_00"]},
                {"role": "user", "text": ["turn_t2i_00_1"]},
                {"role": "model", "text": ["model_t2i_00"]},
            ]),
            ("transcript2instructions_01", [
                {"role": "system", "text": ["system_t2i_01"]},
                {"role": "user", "text": ["turn_t2i_01_1"]},
                {"role": "model", "text": ["model_t2i_01"]},
            ]),
            ("canvasCommandX_00_00", [
                {"role": "system", "text": ["system_00_00"]},
                {"role": "user", "text": ["turn_00_00_1"]},
                {"role": "model", "text": ["turn_00_00_2"]},
                {"role": "user", "text": ["turn_00_00_3"]},
                {"role": "model", "text": ["model_00_00"]},
            ]),
            ("canvasCommandX_00_01", [
                {"role": "system", "text": ["system_00_01"]},
                {"role": "user", "text": ["turn_00_01_1"]},
                {"role": "model", "text": ["turn_00_01_2"]},
                {"role": "user", "text": ["turn_00_01_3"]},
                {"role": "model", "text": ["model_00_01"]},
            ]),
        ],
        [
            ("canvasCommandY_01_00", [
                {"role": "system", "text": ["system_01_00"]},
                {"role": "user", "text": ["turn_01_00_1"]},
                {"role": "model", "text": ["turn_01_00_2"]},
                {"role": "user", "text": ["turn_01_00_3"]},
                {"role": "model", "text": ["model_01_00"]},
            ]),
            ("canvasCommandY_02_00", [
                {"role": "system", "text": ["system_02_00"]},
                {"role": "user", "text": ["turn_02_00_1"]},
                {"role": "model", "text": ["model_02_00"]},
            ]),
        ],
        [],
        [
            ("Questionnaire_06_00", [
                {"role": "system", "text": ["system_06_00"]},
                {"role": "user", "text": ["turn_06_00_1"]},
                {"role": "model", "text": ["model_06_00"]},
            ]),
        ],
    ]
    helper.chatter.return_value.single_conversation.side_effect = [
        "audit01A", "audit01B", "audit02", "audit03", "audit04", "audit05", "audit06"
    ]
    memory_log.instance.side_effect = [
        "memoryLogInstance0",
        "memoryLogInstance1",
        "memoryLogInstance2",
        "memoryLogInstance3",
        "memoryLogInstance4",
        "memoryLogInstance5",
        "memoryLogInstance6",
        "memoryLogInstance7",
    ]
    tested.review(identification, settings, aws_s3_credentials, mock_memory_log, command2uuid, date_x, 4)
    calls = [
        call(aws_s3_credentials),
        call().is_ready(),
        call().upload_text_to_s3('canvasInstance/audits/noteUuid/final_audit_01.log', json.dumps(expected_uploads[0], indent=2)),
        call().upload_text_to_s3('canvasInstance/audits/noteUuid/final_audit_02.log', json.dumps(expected_uploads[1], indent=2)),
        call().upload_text_to_s3('canvasInstance/audits/noteUuid/final_audit_03.log', json.dumps(expected_uploads[2], indent=2)),
        call().upload_text_to_s3('canvasInstance/audits/noteUuid/final_audit_04.log', json.dumps(expected_uploads[3], indent=2)),
    ]
    assert aws_s3.mock_calls == calls
    calls = [
        call.get_discussion('noteUuid'),
    ]
    assert cached_discussion.mock_calls == calls
    calls = [
        call.chatter(settings, "memoryLogInstance0"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_t2i_00'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_t2i_00_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_t2i_00'])),
        call.chatter().single_conversation(['system_t2i_00'], exp_system_prompts["transcript1"], [schema], None),

        call.chatter(settings, "memoryLogInstance1"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_t2i_01'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_t2i_01_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_t2i_01'])),
        call.chatter().single_conversation(['system_t2i_01'], exp_system_prompts["transcript2"], [schema], None),

        call.chatter(settings, "memoryLogInstance2"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_00_00'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_00_00_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['turn_00_00_2'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_00_00_3'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_00_00'])),
        call.chatter().single_conversation(['system_00_00'], exp_system_prompts["common"], [schema], None),

        call.chatter(settings, "memoryLogInstance3"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_00_01'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_00_01_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['turn_00_01_2'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_00_01_3'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_00_01'])),
        call.chatter().single_conversation(['system_00_01'], exp_system_prompts["common"], [schema], None),

        call.chatter(settings, "memoryLogInstance4"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_01_00'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_01_00_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['turn_01_00_2'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_01_00_3'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_01_00'])),
        call.chatter().single_conversation(['system_01_00'], exp_system_prompts["common"], [schema], None),

        call.chatter(settings, "memoryLogInstance5"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_02_00'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_02_00_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_02_00'])),
        call.chatter().single_conversation(['system_02_00'], exp_system_prompts["common"], [schema], None),

        call.chatter(settings, "memoryLogInstance6"),
        call.chatter().add_prompt(LlmTurn(role='system', text=['system_06_00'])),
        call.chatter().add_prompt(LlmTurn(role='user', text=['turn_06_00_1'])),
        call.chatter().add_prompt(LlmTurn(role='model', text=['model_06_00'])),
        call.chatter().single_conversation(['system_06_00'], exp_system_prompts["questionnaire"], [schema], None),
    ]
    assert helper.mock_calls == calls
    calls = [
        call(aws_s3_credentials, identification, "2025-05-07", 1),
        call().stored_documents(),
        call(aws_s3_credentials, identification, "2025-05-07", 2),
        call().stored_documents(),
        call(aws_s3_credentials, identification, "2025-05-07", 3),
        call().stored_documents(),
        call(aws_s3_credentials, identification, "2025-05-07", 4),
        call().stored_documents(),
    ]
    assert llm_turns_store.mock_calls == calls
    calls = [
        call.instance(identification, 'audit_transcript2instructions_00', aws_s3_credentials),
        call.instance(identification, 'audit_transcript2instructions_01', aws_s3_credentials),
        call.instance(identification, 'audit_canvasCommandX_00_00', aws_s3_credentials),
        call.instance(identification, 'audit_canvasCommandX_00_01', aws_s3_credentials),
        call.instance(identification, 'audit_canvasCommandY_01_00', aws_s3_credentials),
        call.instance(identification, 'audit_canvasCommandY_02_00', aws_s3_credentials),
        call.instance(identification, 'audit_Questionnaire_06_00', aws_s3_credentials),
    ]
    assert memory_log.mock_calls == calls
    calls = [
        call.send_to_user('create the audits...'),
        call.send_to_user('auditing of transcript2instructions_00 (cycle  1)'),
        call.send_to_user('auditing of transcript2instructions_01 (cycle  1)'),
        call.send_to_user('auditing of canvasCommandX_00_00 (cycle  1)'),
        call.send_to_user('auditing of canvasCommandX_00_01 (cycle  1)'),
        call.send_to_user('auditing of canvasCommandY_01_00 (cycle  2)'),
        call.send_to_user('auditing of canvasCommandY_02_00 (cycle  2)'),
        # no cycle 3 since there are no document
        call.send_to_user('auditing of Questionnaire_06_00 (cycle  4)'),
        call.send_to_user('audits done')
    ]
    assert mock_memory_log.mock_calls == calls
    reset_mocks()
