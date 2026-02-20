"""Tests for template_permissions module."""

from unittest.mock import MagicMock, call, patch

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.template_permissions import TemplatePermissions


def test_command_permissions_key_prefix():
    tested = Constants
    result = tested.TEMPLATE_COMMAND_PERMISSIONS_KEY_PREFIX
    expected = "note_template_cmd_perms_"
    assert result == expected


class TestTemplatePermissions:
    def teardown_method(self):
        TemplatePermissions.PERMISSIONS.clear()

    def test_init(self):
        tested = TemplatePermissions("test-note-uuid")
        assert tested.note_uuid == "test-note-uuid"

    def test_del_cleans_up_permissions(self):
        TemplatePermissions.PERMISSIONS["test-note-uuid"] = {"SomeCommand": {}}
        tested = TemplatePermissions("test-note-uuid")
        del tested
        assert "test-note-uuid" not in TemplatePermissions.PERMISSIONS

    def test_del_no_error_when_missing(self):
        tested = TemplatePermissions("test-note-uuid")
        del tested
        assert "test-note-uuid" not in TemplatePermissions.PERMISSIONS

    @patch.object(TemplatePermissions, "default_cache_getter")
    def test_load_permissions_success(self, mock_cache_getter):
        mock_cache = MagicMock()
        mock_cache.get.side_effect = [
            {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        ]
        mock_cache_getter.side_effect = [mock_cache]
        tested = TemplatePermissions("test-note-uuid")

        result = tested.load_permissions()
        expected = {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        assert result == expected

        calls = [call()]
        assert mock_cache_getter.mock_calls == calls
        calls = [call.get("note_template_cmd_perms_test-note-uuid", default={})]
        assert mock_cache.mock_calls == calls

    @patch.object(TemplatePermissions, "default_cache_getter")
    def test_load_permissions_empty(self, mock_cache_getter):
        mock_cache = MagicMock()
        mock_cache.get.side_effect = [{}]
        mock_cache_getter.side_effect = [mock_cache]
        tested = TemplatePermissions("test-note-uuid")

        result = tested.load_permissions()
        expected = {}
        assert result == expected

        calls = [call()]
        assert mock_cache_getter.mock_calls == calls
        calls = [call.get("note_template_cmd_perms_test-note-uuid", default={})]
        assert mock_cache.mock_calls == calls

    @patch.object(TemplatePermissions, "default_cache_getter")
    def test_load_permissions_caches_result(self, mock_cache_getter):
        mock_cache = MagicMock()
        mock_cache.get.side_effect = [{"SomeCommand": {"plugin_can_edit": True}}]
        mock_cache_getter.side_effect = [mock_cache]
        tested = TemplatePermissions("test-note-uuid")

        result1 = tested.load_permissions()
        result2 = tested.load_permissions()
        assert result1 == result2

        calls = [call()]
        assert mock_cache_getter.mock_calls == calls
        calls = [call.get("note_template_cmd_perms_test-note-uuid", default={})]
        assert mock_cache.mock_calls == calls

    def test_load_permissions_import_error(self):
        with patch.object(
            TemplatePermissions, "default_cache_getter", side_effect=ImportError("canvas_sdk not available")
        ):
            tested = TemplatePermissions("test-note-uuid")
            result = tested.load_permissions()
            expected = {}
            assert result == expected

    def test_load_permissions_exception(self):
        with patch.object(TemplatePermissions, "default_cache_getter", side_effect=RuntimeError("Cache unavailable")):
            tested = TemplatePermissions("test-note-uuid")
            result = tested.load_permissions()
            expected = {}
            assert result == expected

    @patch.object(TemplatePermissions, "default_cache_getter")
    def test_multiple_notes_separate_caches(self, mock_cache_getter):
        mock_cache = MagicMock()
        mock_cache.get.side_effect = [
            {"CommandA": {"plugin_can_edit": True}},
            {"CommandB": {"plugin_can_edit": False}},
        ]
        mock_cache_getter.side_effect = [mock_cache, mock_cache]
        tested1 = TemplatePermissions("note-uuid-1")
        tested2 = TemplatePermissions("note-uuid-2")

        result = tested1.load_permissions()
        expected = {"CommandA": {"plugin_can_edit": True}}
        assert result == expected

        result = tested2.load_permissions()
        expected = {"CommandB": {"plugin_can_edit": False}}
        assert result == expected

        calls = [call(), call()]
        assert mock_cache_getter.mock_calls == calls
        calls = [
            call.get("note_template_cmd_perms_note-uuid-1", default={}),
            call.get("note_template_cmd_perms_note-uuid-2", default={}),
        ]
        assert mock_cache.mock_calls == calls

    @patch.object(TemplatePermissions, "default_cache_getter")
    def test_shared_class_cache_single_load(self, mock_cache_getter):
        """Two instances for the same note_uuid share the class-level PERMISSIONS dict."""
        mock_cache = MagicMock()
        mock_cache.get.side_effect = [{"CommandA": {"plugin_can_edit": True}}]
        mock_cache_getter.side_effect = [mock_cache]

        instance1 = TemplatePermissions("note-uuid-1")
        instance2 = TemplatePermissions("note-uuid-1")

        result1 = instance1.load_permissions()
        expected = {"CommandA": {"plugin_can_edit": True}}
        assert result1 == expected

        result2 = instance2.load_permissions()
        assert result2 == expected

        calls = [call()]
        assert mock_cache_getter.mock_calls == calls
        calls = [call.get("note_template_cmd_perms_note-uuid-1", default={})]
        assert mock_cache.mock_calls == calls


class TestDefaultCacheGetter:
    def test_default_cache_getter_with_sdk_available(self):
        from hyperscribe.libraries import template_permissions

        original_get_cache_client = template_permissions._get_cache_client
        try:
            mock_cache = MagicMock()
            template_permissions._get_cache_client = MagicMock(return_value=mock_cache)

            tested = TemplatePermissions
            result = tested.default_cache_getter()
            expected = mock_cache
            assert result == expected

            calls = [call(driver="plugins", prefix="note_template_permissions")]
            assert template_permissions._get_cache_client.mock_calls == calls
        finally:
            template_permissions._get_cache_client = original_get_cache_client

    def test_template_permissions_uses_default_cache_getter(self):
        from hyperscribe.libraries import template_permissions

        original_get_cache = template_permissions._get_cache_client
        try:
            mock_cache = MagicMock()
            mock_cache.get.return_value = {"TestCommand": {"plugin_can_edit": True}}
            template_permissions._get_cache_client = MagicMock(return_value=mock_cache)

            TemplatePermissions.PERMISSIONS.clear()
            tested = TemplatePermissions("test-note-uuid")
            result = tested.load_permissions()
            expected = {"TestCommand": {"plugin_can_edit": True}}
            assert result == expected

            calls = [call(driver="plugins", prefix="note_template_permissions")]
            assert template_permissions._get_cache_client.mock_calls == calls
            calls = [call.get("note_template_cmd_perms_test-note-uuid", default={})]
            assert mock_cache.mock_calls == calls
        finally:
            template_permissions._get_cache_client = original_get_cache
            TemplatePermissions.PERMISSIONS.clear()
