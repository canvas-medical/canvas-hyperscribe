from argparse import Namespace
from datetime import datetime, timezone, UTC
from pathlib import Path
from unittest.mock import patch, call, MagicMock

import pytest
from canvas_generated.messages.effects_pb2 import Effect
from canvas_sdk.test_utils import factories
from canvas_sdk.v1.data import Command

from evaluations.case_builders.builder_base import BuilderBase
from evaluations.datastores.datastore_case import DatastoreCase
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def test_validate_files():
    tested = BuilderBase
    tests = [(__file__, Path(__file__), ""), ("nope", None, "'nope' is not a valid file")]
    for file, exp_path, exp_error in tests:
        if exp_path is None:
            with pytest.raises(Exception) as e:
                _ = tested.validate_files(file)
            assert str(e.value) == exp_error
        else:
            result = tested.validate_files(file)
            assert result == exp_path


def test_validate_patient():
    tested = BuilderBase

    # patient not found
    with pytest.raises(Exception) as e:
        _ = tested.validate_patient("patientUuid")
    expected = "'patientUuid' is not a valid patient uuid"
    assert str(e.value) == expected

    # patient is found
    patient = factories.PatientFactory()
    result = tested.validate_patient(patient.id)
    expected = patient.id
    assert result == expected


def test__parameters():
    tested = BuilderBase
    with pytest.raises(NotImplementedError):
        _ = tested._parameters()


def test__run():
    auditor = MagicMock()

    def reset_mocks():
        auditor.reset_mock()

    tested = BuilderBase
    with pytest.raises(NotImplementedError):
        _ = tested._run(
            Namespace(),
            auditor,
            IdentificationParameters(
                patient_uuid="patientUuid",
                note_uuid="noteUuid",
                provider_uuid="providerUuid",
                canvas_instance="canvasInstance",
            ),
        )
        calls = []
        assert auditor.mock_calls == calls
        reset_mocks()


@patch("evaluations.case_builders.builder_base.datetime", wraps=datetime)
@patch("evaluations.case_builders.builder_base.MemoryLog")
@patch("evaluations.case_builders.builder_base.LlmDecisionsReviewer")
@patch("evaluations.case_builders.builder_base.HelperEvaluation")
@patch("evaluations.case_builders.builder_base.CachedSdk")
@patch("evaluations.case_builders.builder_base.BuilderAuditUrl")
@patch("evaluations.case_builders.builder_base.AwsS3")
@patch.object(DatastoreCase, "already_generated")
@patch.object(BuilderBase, "_parameters")
@patch.object(BuilderBase, "_run")
def test_run(
    run,
    parameters,
    already_generated,
    aws_s3,
    builder_audit_url,
    cached_discussion,
    helper,
    llm_decisions_reviewer,
    memory_log,
    mock_datetime,
    capsys,
):
    mock_auditor = MagicMock()

    def reset_mocks():
        run.reset_mock()
        parameters.reset_mock()
        already_generated.reset_mock()
        aws_s3.reset_mock()
        builder_audit_url.reset_mock()
        cached_discussion.reset_mock()
        helper.reset_mock()
        llm_decisions_reviewer.reset_mock()
        memory_log.reset_mock()
        mock_datetime.reset_mock()
        mock_auditor.reset_mock()

    identifications = {
        "target": IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid="noteUuid",
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        ),
        "generic": IdentificationParameters(
            patient_uuid="_PatientUuid",
            note_uuid="_NoteUuid",
            provider_uuid="_ProviderUuid",
            canvas_instance="canvasInstance",
        ),
    }
    dates = [
        datetime(2025, 3, 9, 7, 48, 21, tzinfo=timezone.utc),
        datetime(2025, 3, 10, 7, 55, 37, tzinfo=timezone.utc),
        datetime(2025, 3, 11, 7, 55, 41, tzinfo=timezone.utc),
    ]
    discussion = CachedSdk("noteUuid")
    discussion.cycle = 3
    discussion.created = dates[0]

    tested = BuilderBase()

    # the case has already been generated
    tests = [
        # -- no overwrite argument
        Namespace(case="theCase"),
        # -- overwrite argument False
        Namespace(case="theCase", patient="patientUuid", overwrite=False),
    ]
    for parameter_effect in tests:
        run.side_effect = []
        parameters.side_effect = [parameter_effect]
        already_generated.side_effect = [True]
        aws_s3.return_value.is_ready.side_effect = []
        cached_discussion.side_effect = []
        helper.side_effect = []
        memory_log.end_session.side_effect = []
        mock_datetime.now.side_effect = []

        result = tested.run()
        assert result is None

        exp_out = ["Case 'theCase' already generated", ""]
        assert capsys.readouterr().out == "\n".join(exp_out)

        assert run.mock_calls == []
        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [call("theCase")]
        assert already_generated.mock_calls == calls
        assert aws_s3.mock_calls == []
        assert builder_audit_url.mock_calls == []
        assert cached_discussion.mock_calls == []
        assert helper.mock_calls == []
        assert llm_decisions_reviewer.mock_calls == []
        assert memory_log.mock_calls == []
        assert mock_datetime.mock_calls == []
        assert mock_auditor.mock_calls == []
        reset_mocks()

    error = RuntimeError("There was an error")
    tests_error = [(None, False), (error, True)]
    for run_side_effect, has_error in tests_error:
        # auditor is ready
        tests = [(True, True), (True, False), (False, True), (False, False)]
        # -- patient is provided
        for aws_is_ready, audit_llm in tests:
            arguments = Namespace(case="theCase", patient="patientUuid", overwrite=True)  # <-- overwrite is True

            settings = Settings(
                llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
                llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
                structured_rfv=True,
                audit_llm=audit_llm,
                reasoning_llm=False,
                custom_prompts=[],
                is_tuning=False,
                api_signing_key="theApiSigningKey",
                max_workers=3,
                send_progress=False,
                commands_policy=AccessPolicy(policy=False, items=[]),
                staffers_policy=AccessPolicy(policy=False, items=[]),
                trial_staffers_policy=AccessPolicy(policy=True, items=[]),
                cycle_transcript_overlap=37,
            )

            run.side_effect = [run_side_effect]
            parameters.side_effect = [arguments]
            already_generated.side_effect = [False]
            aws_s3.return_value.is_ready.side_effect = [aws_is_ready]
            cached_discussion.get_discussion.side_effect = [discussion]
            helper.get_auditor.side_effect = [mock_auditor]
            helper.get_note_uuid.side_effect = ["noteUuid"]
            helper.get_provider_uuid.side_effect = ["providerUuid"]
            helper.get_canvas_instance.side_effect = ["canvasInstance"]
            helper.trace_error.side_effect = [{"error": "test"}]
            memory_log.end_session.side_effect = ["flushedMemoryLog"]
            mock_datetime.now.side_effect = [dates[1]]
            mock_auditor.s3_credentials = "awsS3CredentialsInstance1"
            mock_auditor.settings = settings
            mock_auditor.generate_html_summary.return_value.as_uri.side_effect = ["summaryHTML.uri"]

            result = tested.run()
            assert result is None

            exp_out = ["Summary can be viewed at: summaryHTML.uri"]
            if aws_is_ready:
                exp_out.append("Logs saved in: hyperscribe-canvasInstance/finals/2025-03-10/theCase.log")
            exp_out.append("")
            assert capsys.readouterr().out == "\n".join(exp_out)
            calls = [call(arguments, mock_auditor, identifications["target"])]
            assert run.mock_calls == calls
            calls = [call()]
            assert parameters.mock_calls == calls
            calls = [
                call.get_note_uuid("patientUuid"),
                call.get_provider_uuid("patientUuid"),
                call.get_canvas_instance(),
                call.get_auditor("theCase", 0),
            ]
            if has_error:
                calls.extend([call.trace_error(error)])
            assert helper.mock_calls == calls
            calls = [call("awsS3CredentialsInstance1"), call().__bool__(), call().is_ready()]
            if aws_is_ready:
                calls.append(
                    call().upload_text_to_s3(
                        "hyperscribe-canvasInstance/finals/2025-03-10/theCase.log",
                        "flushedMemoryLog",
                    ),
                )
            assert aws_s3.mock_calls == calls
            calls = []
            if aws_is_ready and audit_llm:
                calls = [call.presigned_url("patientUuid", "noteUuid")]
            assert builder_audit_url.mock_calls == calls
            calls = []
            if aws_is_ready and audit_llm:
                calls = [call.get_discussion("noteUuid")]
            assert cached_discussion.mock_calls == calls
            calls = []
            if aws_is_ready and audit_llm:
                calls = [call.review(identifications["target"], settings, "awsS3CredentialsInstance1", {}, dates[0], 3)]
            assert llm_decisions_reviewer.mock_calls == calls
            calls = [call(identifications["target"], "case_builder")]
            if aws_is_ready:
                calls.append(call.end_session("noteUuid"))
            assert memory_log.mock_calls == calls
            calls = []
            if aws_is_ready:
                calls.append(call.now(UTC))
            assert mock_datetime.mock_calls == calls
            calls = [
                call.case_prepare(),
                call.case_finalize({"error": "test"} if has_error else {}, 0),
                call.generate_html_summary(),
                call.generate_html_summary().as_uri(),
            ]
            assert mock_auditor.mock_calls == calls
            reset_mocks()

        # -- patient is NOT provided
        for aws_is_ready, audit_llm in tests:
            arguments = Namespace(case="theCase")

            settings = Settings(
                llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
                llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
                structured_rfv=True,
                audit_llm=audit_llm,
                reasoning_llm=False,
                custom_prompts=[],
                is_tuning=False,
                api_signing_key="theApiSigningKey",
                max_workers=3,
                send_progress=False,
                commands_policy=AccessPolicy(policy=False, items=[]),
                staffers_policy=AccessPolicy(policy=False, items=[]),
                trial_staffers_policy=AccessPolicy(policy=True, items=[]),
                cycle_transcript_overlap=37,
            )

            run.side_effect = [run_side_effect]
            parameters.side_effect = [arguments]
            already_generated.side_effect = [False]
            aws_s3.return_value.is_ready.side_effect = [aws_is_ready]
            cached_discussion.get_discussion.side_effect = [discussion]
            helper.get_auditor.side_effect = [mock_auditor]
            helper.get_note_uuid.side_effect = ["noteUuid"]
            helper.get_provider_uuid.side_effect = ["providerUuid"]
            helper.get_canvas_instance.side_effect = ["canvasInstance"]
            helper.settings.side_effect = [settings]
            helper.trace_error.side_effect = [{"error": "test"}]
            memory_log.end_session.side_effect = ["flushedMemoryLog"]
            mock_datetime.now.side_effect = [dates[2]]
            mock_auditor.s3_credentials = "awsS3CredentialsInstance1"
            mock_auditor.settings = settings
            mock_auditor.generate_html_summary.return_value.as_uri.side_effect = ["summaryHTML.uri"]

            result = tested.run()
            assert result is None

            exp_out = ["Summary can be viewed at: summaryHTML.uri"]
            if aws_is_ready:
                exp_out.append("Logs saved in: hyperscribe-canvasInstance/finals/2025-03-11/theCase.log")
            exp_out.append("")
            assert capsys.readouterr().out == "\n".join(exp_out)

            calls = [call(arguments, mock_auditor, identifications["generic"])]
            assert run.mock_calls == calls
            calls = [call()]
            assert parameters.mock_calls == calls
            calls = [call.get_canvas_instance(), call.get_auditor("theCase", 0)]
            if has_error:
                calls.extend([call.trace_error(error)])
            assert helper.mock_calls == calls
            calls = [call("awsS3CredentialsInstance1"), call().__bool__(), call().is_ready()]
            if aws_is_ready:
                calls.append(
                    call().upload_text_to_s3(
                        "hyperscribe-canvasInstance/finals/2025-03-11/theCase.log",
                        "flushedMemoryLog",
                    ),
                )
            assert aws_s3.mock_calls == calls
            calls = []
            if aws_is_ready and audit_llm:
                calls = [call.presigned_url("_PatientUuid", "_NoteUuid")]
            assert builder_audit_url.mock_calls == calls
            calls = []
            if aws_is_ready and audit_llm:
                calls = [call.get_discussion("_NoteUuid")]
            assert cached_discussion.mock_calls == calls
            calls = []
            if aws_is_ready and audit_llm:
                calls = [
                    call.review(identifications["generic"], settings, "awsS3CredentialsInstance1", {}, dates[0], 3),
                ]
            assert llm_decisions_reviewer.mock_calls == calls
            calls = [call(identifications["generic"], "case_builder")]
            if aws_is_ready:
                calls.append(call.end_session("_NoteUuid"))
            assert memory_log.mock_calls == calls
            calls = []
            if aws_is_ready:
                calls.append(call.now(UTC))
            assert mock_datetime.mock_calls == calls
            calls = [
                call.case_prepare(),
                call.case_finalize({"error": "test"} if has_error else {}, 0),
                call.generate_html_summary(),
                call.generate_html_summary().as_uri(),
            ]
            assert mock_auditor.mock_calls == calls
            reset_mocks()


@patch("evaluations.case_builders.builder_base.Commander")
@patch("evaluations.case_builders.builder_base.AuditorStore")
def test__run_cycle(auditor_store, commander):
    chatter = MagicMock()

    def reset_mocks():
        auditor_store.reset_mock()
        commander.reset_mock()
        chatter.reset_mock()

    audios = [b"audio1", b"audio2"]
    instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid3",
            index=2,
            instruction="theInstruction3",
            information="theInformation3",
            is_new=False,
            is_updated=True,
        ),
    ]
    effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    lines = [
        Line(speaker="voiceA", text="theText1", start=2.1, end=4.8),
        Line(speaker="voiceB", text="theText2", start=4.8, end=5.7),
        Line(speaker="voiceB", text="theText3", start=5.7, end=8.8),
        Line(speaker="voiceA", text="theText4", start=8.8, end=9.9),
    ]
    previous = [Line(speaker="voiceA", text="theText0", start=0.0, end=2.1)]

    tested = BuilderBase
    # the transcript has not been done yet
    auditor_store.transcript.side_effect = [[]]
    commander.transcript2commands.side_effect = []
    commander.audio2commands.side_effect = [(instructions, effects, "the end of the new transcript")]
    result = tested._run_cycle(auditor_store, audios, chatter, instructions[:2], previous)
    expected = (instructions, "the end of the new transcript")
    assert result == expected

    calls = [call.transcript()]
    assert auditor_store.mock_calls == calls
    calls = [call.audio2commands(auditor_store, audios, chatter, instructions[:2], previous)]
    assert commander.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # the transcript has been done
    auditor_store.transcript.side_effect = [lines]
    commander.transcript2commands.side_effect = [(instructions, effects)]
    commander.audio2commands.side_effect = []
    result = tested._run_cycle(auditor_store, audios, chatter, instructions[:2], previous)
    expected = (instructions, [])
    assert result == expected

    calls = [call.transcript()]
    assert auditor_store.mock_calls == calls
    calls = [call.transcript2commands(auditor_store, lines, chatter, instructions[:2])]
    assert commander.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(Commander, "existing_commands_to_coded_items")
@patch.object(Command, "objects")
def test__limited_cache_from(command_db, existing_commands_to_coded_items):
    def reset_mocks():
        command_db.reset_mock()
        existing_commands_to_coded_items.reset_mock()

    tested = BuilderBase
    command_db.filter.return_value.order_by.side_effect = ["QuerySetCommands"]
    existing_commands_to_coded_items.side_effect = [{}]

    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2"]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )

    result = tested._limited_cache_from(identification, settings)
    assert isinstance(result, LimitedCache)
    assert result.patient_uuid == "thePatient"
    assert result._staged_commands == {}

    calls = [
        call.filter(patient__id="thePatient", note__id="theNoteUuid", state="staged"),
        call.filter().order_by("dbid"),
    ]
    assert command_db.mock_calls == calls
    calls = [call("QuerySetCommands", AccessPolicy(policy=False, items=["Command1", "Command2"]), True)]
    assert existing_commands_to_coded_items.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_base.AuditorStore")
def test__summary_generated_commands(auditor_store):
    def reset_mocks():
        auditor_store.reset_mock()

    exp_auditor_store_calls = [call.get_json("parameters2command"), call.get_json("staged_questionnaires")]

    tested = BuilderBase

    # there are no data for the case
    auditor_store.get_json.side_effect = [{}, {}]
    result = tested._summary_generated_commands(auditor_store)
    assert result == []

    assert auditor_store.mock_calls == exp_auditor_store_calls
    reset_mocks()

    # there are data for the case
    # -- no commands in the content
    tests = [{}, {"cycle_000": {"instructions": [], "commands": []}, "cycle_001": {"instructions": [], "commands": []}}]
    for content in tests:
        auditor_store.get_json.side_effect = [content, content]

        result = tested._summary_generated_commands(auditor_store)
        assert result == []

        assert auditor_store.mock_calls == exp_auditor_store_calls
        reset_mocks()

    # -- with commands in the files
    content = {
        "cycle_000": {
            "instructions": [{"uuid": "uuid1", "information": "theInformation1"}],
            "commands": [
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
            ],
        },
        "cycle_001": {
            "instructions": [
                {"uuid": "uuid1", "information": "theInformation2"},
                {"uuid": "uuid3", "information": "theInformation3"},
            ],
            "commands": [
                {
                    "module": "theModule2",
                    "class": "TheClass2",
                    "attributes": {"command_uuid": ">?<", "note_uuid": ">?<", "attributeZ": "valueZ"},
                },
                {
                    "module": "theModule3",
                    "class": "TheClass3",
                    "attributes": {"command_uuid": ">?<", "note_uuid": ">?<"},
                },
            ],
        },
        "cycle_002": {
            "instructions": [{"uuid": "uuid4", "information": "theInformation4"}],
            "commands": [
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
            ],
        },
    }
    auditor_store.get_json.side_effect = [content, content]

    result = tested._summary_generated_commands(auditor_store)
    expected = [
        # common
        {
            "command": {"attributes": {"attributeZ": "valueZ"}, "class": "TheClass2", "module": "theModule2"},
            "instruction": "theInformation2",
        },
        {"command": {"attributes": {}, "class": "TheClass3", "module": "theModule3"}, "instruction": "theInformation3"},
        {
            "command": {
                "attributes": {"attributeA": "valueA", "attributeB": "valueB", "attributeC": "valueC"},
                "class": "TheClass4",
                "module": "theModule4",
            },
            "instruction": "theInformation4",
        },
        # questionnaires
        {
            "command": {
                "attributes": {"attributeA": "valueA", "attributeB": "valueB", "attributeC": "valueC"},
                "class": "TheClass4",
                "module": "theModule4",
            },
            "instruction": "n/a",
        },
    ]

    assert result == expected

    assert auditor_store.mock_calls == exp_auditor_store_calls
    reset_mocks()


def test__remove_uuids():
    tested = BuilderBase
    tests = [
        (
            {
                "module": "theModule",
                "class": "TheClass",
                "attributes": {
                    "command_uuid": ">?<",
                    "note_uuid": ">?<",
                    "attributeX": "valueX",
                    "attributeY": "valueY",
                },
            },
            {
                "module": "theModule",
                "class": "TheClass",
                "attributes": {"attributeX": "valueX", "attributeY": "valueY"},
            },
        ),
        (
            {
                "module": "theModule",
                "class": "TheClass",
                "attributes": {"attributeX": "valueX", "attributeY": "valueY"},
            },
            {
                "module": "theModule",
                "class": "TheClass",
                "attributes": {"attributeX": "valueX", "attributeY": "valueY"},
            },
        ),
    ]
    for command, expected in tests:
        result = tested._remove_uuids(command)
        assert result == expected


@patch("evaluations.case_builders.builder_base.ImplementedCommands")
@patch("evaluations.case_builders.builder_base.import_module")
@patch.object(BuilderBase, "_post_commands")
@patch.object(BuilderBase, "_summary_generated_commands")
def test__render_in_ui(summary_generated_commands, post_commands, import_module, implemented_commands):
    limited_cache = MagicMock()

    def reset_mocks():
        summary_generated_commands.reset_mock()
        post_commands.reset_mock()
        import_module.reset_mock()
        implemented_commands.reset_mock()
        limited_cache.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
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

    tested = BuilderBase

    # there is no command for the case
    summary_generated_commands.side_effect = [[]]
    limited_cache.staged_commands_as_instructions.side_effect = []
    implemented_commands.schema_key2instruction.side_effect = []
    import_module.side_effect = []

    tested._render_in_ui("theCase", identification, limited_cache)

    calls = [call("theCase")]
    assert summary_generated_commands.mock_calls == calls
    assert post_commands.mock_calls == []
    assert import_module.mock_calls == []
    assert implemented_commands.mock_calls == []
    assert limited_cache.mock_calls == []
    reset_mocks()

    # there are commands for the case
    commands = [
        {
            "instruction": "instruction1",
            "command": {
                "module": "theModule1",
                "class": "TheClass1",
                "attributes": {"attributeX": "valueX", "attributeY": "valueY"},
            },
        },
        {
            "instruction": "instruction2",
            "command": {"module": "theModule1", "class": "TheClass1", "attributes": {"attributeZ": "valueZ"}},
        },
        {"instruction": "instruction3", "command": {"module": "theModule3", "class": "TheClass3", "attributes": {}}},
        {
            "instruction": "instruction4",
            "command": {
                "module": "theModule4",
                "class": "TheClass4",
                "attributes": {"attributeA": "valueA", "attributeB": "valueB", "attributeC": "valueC"},
            },
        },
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

    summary_generated_commands.side_effect = [commands]
    limited_cache.staged_commands_as_instructions.side_effect = [instructions]
    implemented_commands.schema_key2instruction.side_effect = [schema_key2instruction]
    import_module.side_effect = [TheModule, TheModule, TheModule, TheModule]

    tested._render_in_ui("theCase", identification, limited_cache)

    calls = [call("theCase")]
    assert summary_generated_commands.mock_calls == calls
    calls = [
        call(
            [
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
                    "attributes": {"command_uuid": None, "note_uuid": "noteUuid", "attributeZ": "valueZ"},
                },
                {
                    "module": "theModule3",
                    "class": "TheClass3",
                    "attributes": {"command_uuid": None, "note_uuid": "noteUuid"},
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
            ],
        ),
    ]
    assert post_commands.mock_calls == calls

    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls
    calls = [call("theModule1"), call("theModule1"), call("theModule3"), call("theModule4")]
    assert import_module.mock_calls == calls
    calls = [call.staged_commands_as_instructions(schema_key2instruction)]
    assert limited_cache.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_base.Authenticator")
@patch("evaluations.case_builders.builder_base.requests_post")
@patch("evaluations.case_builders.builder_base.HelperEvaluation")
def test__post_commands(helper_evaluation, requests_post, authenticator):
    def reset_mocks():
        helper_evaluation.reset_mock()
        requests_post.reset_mock()
        authenticator.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )

    tested = BuilderBase

    helper_evaluation.settings.side_effect = [settings]
    helper_evaluation.get_canvas_host.side_effect = ["https://theHost"]
    requests_post.side_effect = ["postResponse"]
    authenticator.presigned_url.side_effect = ["thePresignedUrl"]

    result = tested._post_commands([{"key1": "value1", "key2": "value2"}])
    assert result == "postResponse"

    calls = [call.settings(), call.get_canvas_host()]
    assert helper_evaluation.mock_calls == calls
    calls = [call.presigned_url("theApiSigningKey", "https://theHost/plugin-io/api/hyperscribe/case_builder", {})]
    assert authenticator.mock_calls == calls
    calls = [
        call(
            "thePresignedUrl",
            headers={"Content-Type": "application/json"},
            json=[{"key1": "value1", "key2": "value2"}],
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()
