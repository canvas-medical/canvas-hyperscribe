"""Tests for template_permissions module."""

import importlib
import sys
from unittest.mock import MagicMock

import pytest

from hyperscribe.libraries.template_permissions import TemplatePermissions


def make_mock_cache(data: dict) -> MagicMock:
    mock_cache = MagicMock()
    mock_cache.get.return_value = data
    return mock_cache


def make_cache_getter(mock_cache: MagicMock):
    return lambda: mock_cache


class TestTemplatePermissions:
    def test_init(self):
        tested = TemplatePermissions("test-note-uuid")
        assert tested.note_uuid == "test-note-uuid"
        assert tested._permissions_cache is None

    def test_init_with_cache_getter(self):
        mock_cache = make_mock_cache({})
        cache_getter = make_cache_getter(mock_cache)
        tested = TemplatePermissions("test-note-uuid", cache_getter=cache_getter)
        assert tested._cache_getter == cache_getter

    def test_load_permissions_success(self):
        mock_cache = make_mock_cache(
            {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result = tested._load_permissions()
        assert result == {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        mock_cache.get.assert_called_once_with("note_template_cmd_perms_test-note-uuid", default={})

    def test_load_permissions_caches_result(self):
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result1 = tested._load_permissions()
        result2 = tested._load_permissions()
        assert result1 == result2
        assert mock_cache.get.call_count == 1

    def test_load_permissions_import_error(self):
        def raise_import_error():
            raise ImportError("canvas_sdk not available")

        tested = TemplatePermissions("test-note-uuid", cache_getter=raise_import_error)
        assert tested._load_permissions() == {}

    def test_load_permissions_exception(self):
        def raise_runtime_error():
            raise RuntimeError("Cache unavailable")

        tested = TemplatePermissions("test-note-uuid", cache_getter=raise_runtime_error)
        assert tested._load_permissions() == {}

    def test_has_template_applied_true(self):
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.has_template_applied() is True

    def test_has_template_applied_false(self):
        mock_cache = make_mock_cache({})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.has_template_applied() is False

    def test_can_edit_command_no_template(self):
        mock_cache = make_mock_cache({})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("HistoryOfPresentIllness") is True

    def test_can_edit_command_allowed(self):
        mock_cache = make_mock_cache(
            {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("HistoryOfPresentIllness") is True

    def test_can_edit_command_denied(self):
        mock_cache = make_mock_cache({"PlanCommand": {"plugin_can_edit": False, "field_permissions": []}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("Plan") is False

    def test_can_edit_command_missing_key_defaults_true(self):
        mock_cache = make_mock_cache({"SomeCommand": {"field_permissions": []}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("Some") is True

    def test_can_edit_field_no_template(self):
        mock_cache = make_mock_cache({})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("HistoryOfPresentIllness", "narrative") is True

    def test_can_edit_field_command_not_editable(self):
        mock_cache = make_mock_cache(
            {
                "PlanCommand": {
                    "plugin_can_edit": False,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Plan", "narrative") is False

    def test_can_edit_field_field_permission_allowed(self):
        mock_cache = make_mock_cache(
            {
                "AssessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {"field_name": "narrative", "plugin_can_edit": True},
                        {"field_name": "background", "plugin_can_edit": False},
                    ],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Assess", "narrative") is True
        assert tested.can_edit_field("Assess", "background") is False

    def test_can_edit_field_no_specific_permission_inherits(self):
        mock_cache = make_mock_cache({"AssessCommand": {"plugin_can_edit": True, "field_permissions": []}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Assess", "some_other_field") is True

    def test_can_edit_field_missing_plugin_can_edit_defaults_true(self):
        mock_cache = make_mock_cache(
            {
                "AssessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative"}],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Assess", "narrative") is True

    def test_get_add_instructions_no_template(self):
        mock_cache = make_mock_cache({})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_add_instructions("HistoryOfPresentIllness", "narrative") == []

    def test_get_add_instructions_with_instructions(self):
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {
                            "field_name": "narrative",
                            "plugin_can_edit": True,
                            "add_instructions": ["symptoms", "duration", "severity"],
                        }
                    ],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result = tested.get_add_instructions("HistoryOfPresentIllness", "narrative")
        assert result == ["symptoms", "duration", "severity"]

    def test_get_add_instructions_field_not_found(self):
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "other_field", "add_instructions": ["foo"]}],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_add_instructions("HistoryOfPresentIllness", "narrative") == []

    def test_get_add_instructions_missing_key(self):
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_add_instructions("HistoryOfPresentIllness", "narrative") == []

    def test_get_edit_framework_no_template(self):
        mock_cache = make_mock_cache({})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_edit_framework("HistoryOfPresentIllness", "narrative") is None

    def test_get_edit_framework_with_framework(self):
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {
                            "field_name": "narrative",
                            "plugin_can_edit": True,
                            "plugin_edit_framework": "Patient is a [AGE] year old [GENDER].",
                        }
                    ],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        framework = tested.get_edit_framework("HistoryOfPresentIllness", "narrative")
        assert framework == "Patient is a [AGE] year old [GENDER]."

    def test_get_edit_framework_field_not_found(self):
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "other_field", "plugin_edit_framework": "some framework"}],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_edit_framework("HistoryOfPresentIllness", "narrative") is None

    def test_get_edit_framework_missing_key(self):
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_edit_framework("HistoryOfPresentIllness", "narrative") is None

    def test_clear_cache(self):
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        tested._load_permissions()
        assert tested._permissions_cache is not None
        tested.clear_cache()
        assert tested._permissions_cache is None
        tested._load_permissions()
        assert mock_cache.get.call_count == 2


class TestTemplatePermissionsEdgeCases:
    def test_empty_field_permissions_list(self):
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True, "field_permissions": []}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Some", "any_field") is True
        assert tested.get_add_instructions("Some", "any_field") == []

    def test_missing_field_permissions_key(self):
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Some", "any_field") is True
        assert tested.get_add_instructions("Some", "any_field") == []

    def test_field_permission_without_field_name(self):
        mock_cache = make_mock_cache(
            {"SomeCommand": {"plugin_can_edit": True, "field_permissions": [{"plugin_can_edit": True}]}}
        )
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("Some", "narrative") is True
        assert tested.get_add_instructions("Some", "narrative") == []

    def test_multiple_notes_separate_caches(self):
        mock_cache1 = make_mock_cache({"CommandA": {"plugin_can_edit": True}})
        mock_cache2 = make_mock_cache({"CommandB": {"plugin_can_edit": False}})
        tested1 = TemplatePermissions("note-uuid-1", cache_getter=make_cache_getter(mock_cache1))
        tested2 = TemplatePermissions("note-uuid-2", cache_getter=make_cache_getter(mock_cache2))
        assert tested1._load_permissions() == {"CommandA": {"plugin_can_edit": True}}
        assert tested2._load_permissions() == {"CommandB": {"plugin_can_edit": False}}

    def test_command_type_not_in_permissions(self):
        mock_cache = make_mock_cache({"SomeOtherCommand": {"plugin_can_edit": True}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("NotInPermissions") is True
        assert tested.can_edit_field("NotInPermissions", "any_field") is True
        assert tested.get_add_instructions("NotInPermissions", "any_field") == []


class TestDefaultCacheGetter:
    def test_default_cache_getter_with_sdk_available(self):
        from hyperscribe.libraries import template_permissions

        original_get_cache_client = template_permissions._get_cache_client
        try:
            mock_cache = MagicMock()
            template_permissions._get_cache_client = MagicMock(return_value=mock_cache)
            result = template_permissions._default_cache_getter()
            assert result == mock_cache
            template_permissions._get_cache_client.assert_called_once_with(
                driver="plugins", prefix="note_template_permissions"
            )
        finally:
            template_permissions._get_cache_client = original_get_cache_client

    def test_default_cache_getter_with_sdk_unavailable(self):
        from hyperscribe.libraries import template_permissions

        original_get_cache = template_permissions._get_cache_client
        try:
            template_permissions._get_cache_client = None
            with pytest.raises(ImportError) as exc_info:
                template_permissions._default_cache_getter()
            assert "canvas_sdk.caching.client not available" in str(exc_info.value)
        finally:
            template_permissions._get_cache_client = original_get_cache

    def test_template_permissions_uses_default_cache_getter(self):
        from hyperscribe.libraries import template_permissions

        original_get_cache = template_permissions._get_cache_client
        try:
            mock_cache = MagicMock()
            mock_cache.get.return_value = {"TestCommand": {"plugin_can_edit": True}}
            template_permissions._get_cache_client = MagicMock(return_value=mock_cache)
            tested = TemplatePermissions("test-note-uuid")
            result = tested._load_permissions()
            assert result == {"TestCommand": {"plugin_can_edit": True}}
        finally:
            template_permissions._get_cache_client = original_get_cache


def test_module_import_fallback_when_canvas_sdk_unavailable():
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "canvas_sdk.caching.client" or ("canvas_sdk.caching" in name and "client" in str(args)):
            raise ImportError("Mocked: canvas_sdk.caching.client not available")
        return original_import(name, *args, **kwargs)

    modules_to_save = [
        "hyperscribe.libraries.template_permissions",
        "hyperscribe.libraries",
        "hyperscribe",
    ]
    saved_modules = {key: sys.modules.get(key) for key in modules_to_save}

    try:
        for key in modules_to_save:
            if key in sys.modules:
                del sys.modules[key]
        builtins.__import__ = mock_import
        tp_reloaded = importlib.import_module("hyperscribe.libraries.template_permissions")
        assert tp_reloaded._get_cache_client is None
    finally:
        builtins.__import__ = original_import
        for key in modules_to_save:
            if key in sys.modules:
                del sys.modules[key]
        for key, module in saved_modules.items():
            if module is not None:
                sys.modules[key] = module
        importlib.import_module("hyperscribe.libraries.template_permissions")
