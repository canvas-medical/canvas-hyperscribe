import json
from argparse import Namespace
from datetime import datetime, timezone, UTC
from pathlib import Path
from time import time
from unittest.mock import patch, call, MagicMock

import pytest
from canvas_sdk.v1.data import Patient, Command

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.cached_discussion import CachedDiscussion
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def test_validate_files():
    tested = BuilderBase
    tests = [
        (__file__, Path(__file__), ""),
        ("nope", None, "'nope' is not a valid file"),
    ]
    for file, exp_path, exp_error in tests:
        if exp_path is None:
            with pytest.raises(Exception) as e:
                _ = tested.validate_files(file)
            assert str(e.value) == exp_error
        else:
            result = tested.validate_files(file)
            assert result == exp_path


@patch.object(Patient, "objects")
def test_validate_patient(patient_db):
    def reset_mocks():
        patient_db.reset_mock()

    tested = BuilderBase

    # patient not found
    patient_db.filter.side_effect = [[]]
    with pytest.raises(Exception) as e:
        _ = tested.validate_patient("patientUuid")
    expected = "'patientUuid' is not a valid patient uuid"
    assert str(e.value) == expected

    calls = [call.filter(id="patientUuid")]
    assert patient_db.mock_calls == calls
    reset_mocks()

    # patient is found
    patient_db.filter.side_effect = [[Patient(id="patientUuid")]]
    result = tested.validate_patient("patientUuid")
    expected = "patientUuid"
    assert result == expected

    calls = [call.filter(id="patientUuid")]
    assert patient_db.mock_calls == calls
    reset_mocks()


def test__parameters():
    tested = BuilderBase
    with pytest.raises(NotImplementedError):
        _ = tested._parameters()


def test__run():
    tested = BuilderBase
    with pytest.raises(NotImplementedError):
        _ = tested._run(
            Namespace(),
            AuditorFile("theCase"),
            IdentificationParameters(
                patient_uuid="patientUuid",
                note_uuid="noteUuid",
                provider_uuid="providerUuid",
                canvas_instance="canvasInstance",
            ))


@patch("evaluations.case_builders.builder_base.datetime", wraps=datetime)
@patch("evaluations.case_builders.builder_base.MemoryLog")
@patch("evaluations.case_builders.builder_base.LlmDecisionsReviewer")
@patch("evaluations.case_builders.builder_base.HelperEvaluation")
@patch("evaluations.case_builders.builder_base.CachedDiscussion")
@patch("evaluations.case_builders.builder_base.BuilderAuditUrl")
@patch("evaluations.case_builders.builder_base.AwsS3")
@patch("evaluations.case_builders.builder_base.AuditorFile")
@patch.object(BuilderBase, "_parameters")
@patch.object(BuilderBase, "_run")
def test_run(
        run,
        parameters,
        auditor_file,
        aws_s3,
        builder_audit_url,
        cached_discussion,
        helper,
        llm_decisions_reviewer,
        memory_log,
        mock_datetime,
        capsys,
):
    def reset_mocks():
        run.reset_mock()
        parameters.reset_mock()
        auditor_file.reset_mock()
        aws_s3.reset_mock()
        builder_audit_url.reset_mock()
        cached_discussion.reset_mock()
        helper.reset_mock()
        llm_decisions_reviewer.reset_mock()
        memory_log.reset_mock()
        mock_datetime.reset_mock()

    identifications = {
        "target": IdentificationParameters(
            patient_uuid='patientUuid',
            note_uuid='noteUuid',
            provider_uuid='providerUuid',
            canvas_instance="canvasInstance",
        ),
        "generic": IdentificationParameters(
            patient_uuid='_PatientUuid',
            note_uuid='_NoteUuid',
            provider_uuid='_ProviderUuid',
            canvas_instance="canvasInstance",
        ),
    }
    dates = [
        datetime(2025, 3, 9, 7, 48, 21, tzinfo=timezone.utc),
        datetime(2025, 3, 10, 7, 55, 37, tzinfo=timezone.utc),
        datetime(2025, 3, 11, 7, 55, 41, tzinfo=timezone.utc),
    ]
    discussion = CachedDiscussion("noteUuid")
    discussion.cycle = 3
    discussion.created = dates[0]

    tested = BuilderBase()

    # auditor is not ready
    run.side_effect = []
    parameters.side_effect = [Namespace(case="theCase")]
    auditor_file.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.is_ready.side_effect = []
    cached_discussion.side_effect = []
    helper.side_effect = []
    memory_log.end_session.side_effect = []
    mock_datetime.now.side_effect = []

    result = tested.run()
    assert result is None

    exp_out = [
        "Case 'theCase': some files exist already",
        "",
    ]
    assert capsys.readouterr().out == "\n".join(exp_out)

    assert run.mock_calls == []
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [
        call("theCase"),
        call().is_ready(),
    ]
    assert auditor_file.mock_calls == calls
    assert aws_s3.mock_calls == []
    assert builder_audit_url.mock_calls == []
    assert cached_discussion.mock_calls == []
    assert helper.mock_calls == []
    assert llm_decisions_reviewer.mock_calls == []
    assert memory_log.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # auditor is ready
    tests = [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ]
    # -- patient is provided
    for aws_is_ready, audit_llm in tests:
        arguments = Namespace(case="theCase", patient="patientUuid")

        settings = Settings(
            llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
            llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
            science_host='theScienceHost',
            ontologies_host='theOntologiesHost',
            pre_shared_key='thePreSharedKey',
            structured_rfv=True,
            audit_llm=audit_llm,
            api_signing_key="theApiSigningKey",
        )

        run.side_effect = [None]
        parameters.side_effect = [arguments]
        auditor_file.return_value.is_ready.side_effect = [True]
        aws_s3.return_value.is_ready.side_effect = [aws_is_ready]
        cached_discussion.get_discussion.side_effect = [discussion]
        helper.aws_s3_credentials.side_effect = ["awsS3CredentialsInstance1"]
        helper.get_note_uuid.side_effect = ["noteUuid"]
        helper.get_provider_uuid.side_effect = ["providerUuid"]
        helper.get_canvas_instance.side_effect = ["canvasInstance"]
        helper.settings.side_effect = [settings]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        mock_datetime.now.side_effect = [dates[1]]

        result = tested.run()
        assert result is None

        exp_out = []
        if aws_is_ready:
            exp_out.append('Logs saved in: canvasInstance/finals/2025-03-10/theCase.log')
        exp_out.append('')
        assert capsys.readouterr().out == "\n".join(exp_out)
        calls = [call(arguments, auditor_file.return_value, identifications["target"])]
        assert run.mock_calls == calls
        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call.get_note_uuid('patientUuid'),
            call.get_provider_uuid('patientUuid'),
            call.get_canvas_instance(),
            call.aws_s3_credentials(),
        ]
        if aws_is_ready:
            calls.append(call.settings())
        assert helper.mock_calls == calls
        calls = [
            call("theCase"),
            call().is_ready(),
        ]
        assert auditor_file.mock_calls == calls
        calls = [
            call("awsS3CredentialsInstance1"),
            call().__bool__(),
            call().is_ready(),
        ]
        if aws_is_ready:
            calls.append(call().upload_text_to_s3(
                'canvasInstance/finals/2025-03-10/theCase.log',
                "flushedMemoryLog"),
            )
        assert aws_s3.mock_calls == calls
        calls = []
        if aws_is_ready and audit_llm:
            calls = [call.presigned_url('patientUuid', 'noteUuid')]
        assert builder_audit_url.mock_calls == calls
        calls = []
        if aws_is_ready and audit_llm:
            calls = [call.get_discussion('noteUuid')]
        assert cached_discussion.mock_calls == calls
        calls = []
        if aws_is_ready and audit_llm:
            calls = [
                call.review(
                    identifications["target"],
                    settings,
                    'awsS3CredentialsInstance1',
                    memory_log.return_value,
                    {},
                    dates[0],
                    3,
                ),
            ]
        assert llm_decisions_reviewer.mock_calls == calls
        calls = [call(identifications["target"], "case_builder")]
        if aws_is_ready:
            calls.append(call.end_session('noteUuid'))
        assert memory_log.mock_calls == calls
        calls = []
        if aws_is_ready:
            calls.append(call.now(UTC))
        assert mock_datetime.mock_calls == calls
        reset_mocks()

    # -- patient is NOT provided
    for aws_is_ready, audit_llm in tests:
        arguments = Namespace(case="theCase")

        settings = Settings(
            llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
            llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
            science_host='theScienceHost',
            ontologies_host='theOntologiesHost',
            pre_shared_key='thePreSharedKey',
            structured_rfv=True,
            audit_llm=audit_llm,
            api_signing_key="theApiSigningKey",
        )

        run.side_effect = [None]
        parameters.side_effect = [arguments]
        auditor_file.return_value.is_ready.side_effect = [True]
        aws_s3.return_value.is_ready.side_effect = [aws_is_ready]
        cached_discussion.get_discussion.side_effect = [discussion]
        helper.aws_s3_credentials.side_effect = ["awsS3CredentialsInstance1"]
        helper.get_note_uuid.side_effect = ["noteUuid"]
        helper.get_provider_uuid.side_effect = ["providerUuid"]
        helper.get_canvas_instance.side_effect = ["canvasInstance"]
        helper.settings.side_effect = [settings]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        mock_datetime.now.side_effect = [dates[2]]

        result = tested.run()
        assert result is None

        exp_out = []
        if aws_is_ready:
            exp_out.append('Logs saved in: canvasInstance/finals/2025-03-11/theCase.log')
        exp_out.append('')
        assert capsys.readouterr().out == "\n".join(exp_out)

        calls = [call(arguments, auditor_file.return_value, identifications["generic"])]
        assert run.mock_calls == calls
        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call.get_canvas_instance(),
            call.aws_s3_credentials(),
        ]
        if aws_is_ready:
            calls.append(call.settings())
        assert helper.mock_calls == calls
        calls = [
            call("theCase"),
            call().is_ready(),
        ]
        assert auditor_file.mock_calls == calls
        calls = [
            call("awsS3CredentialsInstance1"),
            call().__bool__(),
            call().is_ready(),
        ]
        if aws_is_ready:
            calls.append(call().upload_text_to_s3(
                'canvasInstance/finals/2025-03-11/theCase.log',
                "flushedMemoryLog"),
            )
        assert aws_s3.mock_calls == calls
        calls = []
        if aws_is_ready and audit_llm:
            calls = [call.presigned_url('_PatientUuid', '_NoteUuid')]
        assert builder_audit_url.mock_calls == calls
        calls = []
        if aws_is_ready and audit_llm:
            calls = [call.get_discussion('_NoteUuid')]
        assert cached_discussion.mock_calls == calls
        calls = []
        if aws_is_ready and audit_llm:
            calls = [
                call.review(
                    identifications["generic"],
                    settings,
                    'awsS3CredentialsInstance1',
                    memory_log.return_value,
                    {},
                    dates[0],
                    3,
                ),
            ]
        assert llm_decisions_reviewer.mock_calls == calls
        calls = [call(identifications["generic"], "case_builder")]
        if aws_is_ready:
            calls.append(call.end_session('_NoteUuid'))
        assert memory_log.mock_calls == calls
        calls = []
        if aws_is_ready:
            calls.append(call.now(UTC))
        assert mock_datetime.mock_calls == calls
        reset_mocks()


@patch.object(Commander, 'existing_commands_to_coded_items')
@patch.object(Command, "objects")
def test__limited_cache_from(command_db, existing_commands_to_coded_items):
    def reset_mocks():
        command_db.reset_mock()
        existing_commands_to_coded_items.reset_mock()

    tested = BuilderBase
    command_db.filter.return_value.order_by.side_effect = ["QuerySetCommands"]
    existing_commands_to_coded_items.side_effect = [{}]
    result = tested._limited_cache_from(IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    ))
    assert isinstance(result, LimitedCache)
    assert result.patient_uuid == "thePatient"
    assert result._staged_commands == {}

    calls = [
        call.filter(patient__id='thePatient', note__id='theNoteUuid', state='staged'),
        call.filter().order_by('dbid'),
    ]
    assert command_db.mock_calls == calls
    calls = [call("QuerySetCommands")]
    assert existing_commands_to_coded_items.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_base.ImplementedCommands")
@patch("evaluations.case_builders.builder_base.import_module")
@patch("evaluations.case_builders.builder_base.Path")
@patch.object(BuilderBase, "post_commands")
def test__publish_in_ui(post_commands, path, import_module, implemented_commands):
    limited_cache = MagicMock()
    path_file = MagicMock()

    def reset_mocks():
        post_commands.reset_mock()
        path.reset_mock()
        import_module.reset_mock()
        implemented_commands.reset_mock()
        limited_cache.reset_mock()
        path_file.reset_mock()

    identification = IdentificationParameters(
        patient_uuid='patientUuid',
        note_uuid='noteUuid',
        provider_uuid='providerUuid',
        canvas_instance="canvasInstance",
    )
    instructions = [
        Instruction(
            uuid="uuid1",
            index=1,
            instruction="pluginClass1",
            information="theInformation1",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid4",
            index=3,
            instruction="pluginClass4",
            information="theInformation4",
            is_new=True,
            is_updated=False,
        ),
    ]
    schema_key2instruction = {
        "theClass1Key": "pluginClass1",
        "theClass2Key": "pluginClass2",
        "theClass3Key": "pluginClass3",
        "theClass4Key": "pluginClass4",
    }

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tested = BuilderBase

    # there is no files for the case
    path.return_value.parent.parent.__truediv__.side_effect = [path_file, path_file]
    path_file.exists.side_effect = [False, False]
    limited_cache.staged_commands_as_instructions.side_effect = []
    implemented_commands.schema_key2instruction.side_effect = []
    import_module.side_effect = []

    result = tested._publish_in_ui("theCase", identification, limited_cache)
    assert result is None

    assert post_commands.mock_calls == []
    calls = [
        call(f'{directory}/builder_base.py'),
        call().parent.parent.__truediv__('parameters2command/theCase.json'),
        call(f'{directory}/builder_base.py'),
        call().parent.parent.__truediv__('staged_questionnaires/theCase.json'),
    ]
    assert path.mock_calls == calls
    assert import_module.mock_calls == []
    assert implemented_commands.mock_calls == []
    assert limited_cache.mock_calls == []
    calls = [
        call.exists(),
        call.exists(),
    ]
    assert path_file.mock_calls == calls
    reset_mocks()

    # there are files for the case
    # -- no commands in the files (only one file)
    file_contents = [
        json.dumps({"commands": []}),
    ]

    path.return_value.parent.parent.__truediv__.side_effect = [path_file, path_file]
    path_file.exists.side_effect = [True, False]
    path_file.open.return_value.__enter__.return_value.read.side_effect = file_contents
    limited_cache.staged_commands_as_instructions.side_effect = [instructions]
    implemented_commands.schema_key2instruction.side_effect = [schema_key2instruction]
    import_module.side_effect = []

    tested._publish_in_ui("theCase", identification, limited_cache)

    assert post_commands.mock_calls == []
    calls = [
        call(f'{directory}/builder_base.py'),
        call().parent.parent.__truediv__('parameters2command/theCase.json'),
        call(f'{directory}/builder_base.py'),
        call().parent.parent.__truediv__('staged_questionnaires/theCase.json'),
    ]
    assert path.mock_calls == calls
    assert implemented_commands.mock_calls == []
    assert import_module.mock_calls == []
    assert limited_cache.mock_calls == []
    calls = [
        call.exists(),
        call.open('r'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
        call.exists(),
    ]
    assert path_file.mock_calls == calls
    reset_mocks()
    # -- with commands in the files
    file_contents = [
        json.dumps({"commands": [
            {
                "module": "theModule1",
                "class": "TheClass1",
                "attributes": {
                    "command_uuid": ">?<",
                    "note_uuid": ">?<",
                    "attributeX": "valueX",
                    "attributeY": "valueY",
                },
            },
            {
                "module": "theModule1",
                "class": "TheClass1",
                "attributes": {
                    "command_uuid": ">?<",
                    "note_uuid": ">?<",
                    "attributeZ": "valueZ",
                },
            },
            {
                "module": "theModule3",
                "class": "TheClass3",
                "attributes": {
                    "command_uuid": ">?<",
                    "note_uuid": ">?<",
                },
            },
        ]}),
        json.dumps({"commands": [
            {
                "module": "theModule4",
                "class": "TheClass4",
                "attributes": {
                    "command_uuid": ">?<",
                    "note_uuid": ">?<",
                    "attributeA": "valueA",
                    "attributeB": "valueB",
                    "attributeC": "valueC",
                },
            },
        ]}),
    ]

    class TheModule:
        class TheClass1:
            class Meta:
                key = "theClass1Key"

        class TheClass2:
            class Meta:
                key = "theClass2Key"

        class TheClass3:
            class Meta:
                key = "theClass3Key"

        class TheClass4:
            class Meta:
                key = "theClass4Key"

    path.return_value.parent.parent.__truediv__.side_effect = [path_file, path_file]
    path_file.exists.side_effect = [True, True]
    path_file.open.return_value.__enter__.return_value.read.side_effect = file_contents
    limited_cache.staged_commands_as_instructions.side_effect = [instructions]
    implemented_commands.schema_key2instruction.side_effect = [schema_key2instruction]
    import_module.side_effect = [TheModule, TheModule, TheModule, TheModule]

    result = tested._publish_in_ui("theCase", identification, limited_cache)
    assert result is None

    calls = [call([
        {
            "module": "theModule1",
            "class": "TheClass1",
            "attributes": {
                "command_uuid": "uuid1",
                "note_uuid": "noteUuid",
                "attributeX": "valueX",
                "attributeY": "valueY",
            },
        },
        {
            "module": "theModule1",
            "class": "TheClass1",
            "attributes": {
                "command_uuid": None,
                "note_uuid": "noteUuid",
                "attributeZ": "valueZ",
            },
        },
        {
            "module": "theModule3",
            "class": "TheClass3",
            "attributes": {
                "command_uuid": None,
                "note_uuid": "noteUuid",
            },
        },
        {
            "module": "theModule4",
            "class": "TheClass4",
            "attributes": {
                "command_uuid": "uuid4",
                "note_uuid": "noteUuid",
                "attributeA": "valueA",
                "attributeB": "valueB",
                "attributeC": "valueC",
            },
        },
    ])]
    assert post_commands.mock_calls == calls
    calls = [
        call(f'{directory}/builder_base.py'),
        call().parent.parent.__truediv__('parameters2command/theCase.json'),
        call(f'{directory}/builder_base.py'),
        call().parent.parent.__truediv__('staged_questionnaires/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls
    calls = [
        call("theModule1"),
        call("theModule1"),
        call("theModule3"),
        call("theModule4"),
    ]
    assert import_module.mock_calls == calls
    calls = [call.staged_commands_as_instructions(schema_key2instruction)]
    assert limited_cache.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
        call.exists(),
        call.open('r'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]
    assert path_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_base.time", wraps=time)
@patch("evaluations.case_builders.builder_base.requests_post")
@patch("evaluations.case_builders.builder_base.HelperEvaluation")
def test_post_commands(helper_evaluation, requests_post, mock_time):
    def reset_mocks():
        helper_evaluation.reset_mock()
        requests_post.reset_mock()
        mock_time.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=True,
        api_signing_key="theApiSigningKey",
    )

    tested = BuilderBase

    helper_evaluation.settings.side_effect = [settings]
    helper_evaluation.get_canvas_host.side_effect = ["https://theHost"]
    requests_post.side_effect = ["postResponse"]
    mock_time.side_effect = [1747163653.9470942]

    result = tested.post_commands([{"key1": "value1", "key2": "value2"}])
    assert result == "postResponse"

    calls = [
        call.settings(),
        call.get_canvas_host(),
    ]
    assert helper_evaluation.mock_calls == calls
    calls = [call()]
    assert mock_time.mock_calls == calls
    calls = [
        call(
            'https://theHost/plugin-io/api/hyperscribe/case_builder',
            headers={'Content-Type': 'application/json'},
            params={'ts': '1747163653', 'sig': '10b873fcbeef79834cc483520fbbbdf4ed9bc4f8bd4c1a941c40162da30852d7'},
            json=[{'key1': 'value1', 'key2': 'value2'}],
            verify=True,
            timeout=None,
        )
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()
