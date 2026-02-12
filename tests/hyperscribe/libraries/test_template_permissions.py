"""Tests for template_permissions module."""

from unittest.mock import MagicMock, call

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.template_permissions import TemplatePermissions


def make_mock_cache(data: dict) -> MagicMock:
    mock_cache = MagicMock()
    mock_cache.get.return_value = data
    return mock_cache


def make_cache_getter(mock_cache: MagicMock):
    return lambda: mock_cache


def test_command_permissions_key_prefix():
    tested = Constants
    result = tested.TEMPLATE_COMMAND_PERMISSIONS_KEY_PREFIX
    expected = "note_template_cmd_perms_"
    assert result == expected


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

        result = tested.load_permissions()
        expected = {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        assert result == expected

        calls = [call.get("note_template_cmd_perms_test-note-uuid", default={})]
        assert mock_cache.mock_calls == calls

    def test_load_permissions_caches_result(self):
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})
        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))

        result1 = tested.load_permissions()
        result2 = tested.load_permissions()
        assert result1 == result2

        calls = [call.get("note_template_cmd_perms_test-note-uuid", default={})]
        assert mock_cache.mock_calls == calls

    def test_load_permissions_import_error(self):
        def raise_import_error():
            raise ImportError("canvas_sdk not available")

        tested = TemplatePermissions("test-note-uuid", cache_getter=raise_import_error)

        result = tested.load_permissions()
        expected = {}
        assert result == expected

    def test_load_permissions_exception(self):
        def raise_runtime_error():
            raise RuntimeError("Cache unavailable")

        tested = TemplatePermissions("test-note-uuid", cache_getter=raise_runtime_error)

        result = tested.load_permissions()
        expected = {}
        assert result == expected

    def test_multiple_notes_separate_caches(self):
        mock_cache1 = make_mock_cache({"CommandA": {"plugin_can_edit": True}})
        mock_cache2 = make_mock_cache({"CommandB": {"plugin_can_edit": False}})
        tested1 = TemplatePermissions("note-uuid-1", cache_getter=make_cache_getter(mock_cache1))
        tested2 = TemplatePermissions("note-uuid-2", cache_getter=make_cache_getter(mock_cache2))

        result = tested1.load_permissions()
        expected = {"CommandA": {"plugin_can_edit": True}}
        assert result == expected

        result = tested2.load_permissions()
        expected = {"CommandB": {"plugin_can_edit": False}}
        assert result == expected

        calls = [call.get("note_template_cmd_perms_note-uuid-1", default={})]
        assert mock_cache1.mock_calls == calls
        calls = [call.get("note_template_cmd_perms_note-uuid-2", default={})]
        assert mock_cache2.mock_calls == calls


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
