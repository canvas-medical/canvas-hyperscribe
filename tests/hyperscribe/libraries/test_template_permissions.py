"""Tests for template_permissions module."""

from unittest.mock import MagicMock

import pytest

from hyperscribe.libraries.template_permissions import TemplatePermissions


def make_mock_cache(data: dict) -> MagicMock:
    """Create a mock cache object with the given data."""
    mock_cache = MagicMock()
    mock_cache.get.return_value = data
    return mock_cache


def make_cache_getter(mock_cache: MagicMock):
    """Create a cache getter function that returns the mock cache."""
    return lambda: mock_cache


class TestTemplatePermissions:
    """Tests for the TemplatePermissions class."""

    def test_init(self):
        """Test initialization sets note_uuid and cache is None."""
        tested = TemplatePermissions("test-note-uuid")
        assert tested.note_uuid == "test-note-uuid"
        assert tested._permissions_cache is None

    def test_init_with_cache_getter(self):
        """Test initialization with custom cache getter."""
        mock_cache = make_mock_cache({})
        cache_getter = make_cache_getter(mock_cache)

        tested = TemplatePermissions("test-note-uuid", cache_getter=cache_getter)
        assert tested._cache_getter == cache_getter

    def test_load_permissions_success(self):
        """Test loading permissions from cache successfully."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result = tested._load_permissions()

        assert result == {"HistoryOfPresentIllnessCommand": {"plugin_can_edit": True, "field_permissions": []}}
        mock_cache.get.assert_called_once_with("note_template_cmd_perms_test-note-uuid", default={})

    def test_load_permissions_caches_result(self):
        """Test that permissions are cached and not reloaded."""
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))

        # First call loads from cache
        result1 = tested._load_permissions()
        # Second call uses cached value
        result2 = tested._load_permissions()

        assert result1 == result2
        # cache.get should only be called once
        assert mock_cache.get.call_count == 1

    def test_load_permissions_import_error(self):
        """Test graceful handling of ImportError."""

        def raise_import_error():
            raise ImportError("canvas_sdk not available")

        tested = TemplatePermissions("test-note-uuid", cache_getter=raise_import_error)
        result = tested._load_permissions()

        assert result == {}

    def test_load_permissions_exception(self):
        """Test graceful handling of generic exceptions."""

        def raise_runtime_error():
            raise RuntimeError("Cache unavailable")

        tested = TemplatePermissions("test-note-uuid", cache_getter=raise_runtime_error)
        result = tested._load_permissions()

        assert result == {}

    def test_has_template_applied_true(self):
        """Test has_template_applied returns True when permissions exist."""
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.has_template_applied() is True

    def test_has_template_applied_false(self):
        """Test has_template_applied returns False when no permissions."""
        mock_cache = make_mock_cache({})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.has_template_applied() is False

    def test_can_edit_command_no_template(self):
        """Test can_edit_command returns True when no template applied."""
        mock_cache = make_mock_cache({})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("HistoryOfPresentIllnessCommand") is True

    def test_can_edit_command_allowed(self):
        """Test can_edit_command returns True when plugin_can_edit is True."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("HistoryOfPresentIllnessCommand") is True

    def test_can_edit_command_denied(self):
        """Test can_edit_command returns False when plugin_can_edit is False."""
        mock_cache = make_mock_cache(
            {
                "PlanCommand": {
                    "plugin_can_edit": False,
                    "field_permissions": [],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("PlanCommand") is False

    def test_can_edit_command_missing_key_defaults_true(self):
        """Test can_edit_command defaults to True if plugin_can_edit key missing."""
        mock_cache = make_mock_cache(
            {
                "SomeCommand": {
                    "field_permissions": [],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command("SomeCommand") is True

    def test_can_edit_command_by_class(self):
        """Test can_edit_command_by_class converts class name correctly."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": False,
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_command_by_class("HistoryOfPresentIllness") is False

    def test_can_edit_field_no_template(self):
        """Test can_edit_field returns True when no template applied."""
        mock_cache = make_mock_cache({})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("HistoryOfPresentIllnessCommand", "narrative") is True

    def test_can_edit_field_command_not_editable(self):
        """Test can_edit_field returns False when command not editable."""
        mock_cache = make_mock_cache(
            {
                "PlanCommand": {
                    "plugin_can_edit": False,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        # Even though field says editable, command-level blocks it
        assert tested.can_edit_field("PlanCommand", "narrative") is False

    def test_can_edit_field_field_permission_allowed(self):
        """Test can_edit_field respects field-level permission when allowed."""
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
        assert tested.can_edit_field("AssessCommand", "narrative") is True
        assert tested.can_edit_field("AssessCommand", "background") is False

    def test_can_edit_field_no_specific_permission_inherits(self):
        """Test can_edit_field inherits from command when no field permission."""
        mock_cache = make_mock_cache(
            {
                "AssessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        # Field not in permissions list, inherits from command
        assert tested.can_edit_field("AssessCommand", "some_other_field") is True

    def test_can_edit_field_missing_plugin_can_edit_defaults_true(self):
        """Test field defaults to editable if plugin_can_edit key missing."""
        mock_cache = make_mock_cache(
            {
                "AssessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {"field_name": "narrative"}  # Missing plugin_can_edit
                    ],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field("AssessCommand", "narrative") is True

    def test_can_edit_field_by_class(self):
        """Test can_edit_field_by_class converts class name correctly."""
        mock_cache = make_mock_cache(
            {
                "AssessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": False}],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.can_edit_field_by_class("Assess", "narrative") is False

    def test_get_add_instructions_no_template(self):
        """Test get_add_instructions returns empty list when no template."""
        mock_cache = make_mock_cache({})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_add_instructions("HistoryOfPresentIllnessCommand", "narrative") == []

    def test_get_add_instructions_with_instructions(self):
        """Test get_add_instructions returns instructions from template."""
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
        result = tested.get_add_instructions("HistoryOfPresentIllnessCommand", "narrative")
        assert result == ["symptoms", "duration", "severity"]

    def test_get_add_instructions_field_not_found(self):
        """Test get_add_instructions returns empty list when field not found."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "other_field", "add_instructions": ["foo"]}],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_add_instructions("HistoryOfPresentIllnessCommand", "narrative") == []

    def test_get_add_instructions_missing_key(self):
        """Test get_add_instructions returns empty list when add_instructions key missing."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_add_instructions("HistoryOfPresentIllnessCommand", "narrative") == []

    def test_get_add_instructions_by_class(self):
        """Test get_add_instructions_by_class converts class name correctly."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "add_instructions": ["symptoms"]}],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result = tested.get_add_instructions_by_class("HistoryOfPresentIllness", "narrative")
        assert result == ["symptoms"]

    def test_get_editable_fields_no_template(self):
        """Test get_editable_fields returns None when no template."""
        mock_cache = make_mock_cache({})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_editable_fields("HistoryOfPresentIllnessCommand") is None

    def test_get_editable_fields_command_not_editable(self):
        """Test get_editable_fields returns empty set when command not editable."""
        mock_cache = make_mock_cache(
            {
                "PlanCommand": {
                    "plugin_can_edit": False,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        assert tested.get_editable_fields("PlanCommand") == set()

    def test_get_editable_fields_mixed_permissions(self):
        """Test get_editable_fields returns only editable fields."""
        mock_cache = make_mock_cache(
            {
                "AssessCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {"field_name": "narrative", "plugin_can_edit": True},
                        {"field_name": "background", "plugin_can_edit": False},
                        {"field_name": "status", "plugin_can_edit": True},
                    ],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result = tested.get_editable_fields("AssessCommand")
        assert result == {"narrative", "status"}

    def test_get_all_command_types_with_restrictions(self):
        """Test get_all_command_types_with_restrictions returns command type list."""
        mock_cache = make_mock_cache(
            {
                "HistoryOfPresentIllnessCommand": {"plugin_can_edit": True},
                "PlanCommand": {"plugin_can_edit": False},
                "AssessCommand": {"plugin_can_edit": True},
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        result = tested.get_all_command_types_with_restrictions()
        assert sorted(result) == ["AssessCommand", "HistoryOfPresentIllnessCommand", "PlanCommand"]

    def test_clear_cache(self):
        """Test clear_cache resets the cached permissions."""
        mock_cache = make_mock_cache({"SomeCommand": {"plugin_can_edit": True}})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))

        # Load permissions
        tested._load_permissions()
        assert tested._permissions_cache is not None

        # Clear cache
        tested.clear_cache()
        assert tested._permissions_cache is None

        # Reload should call cache again
        tested._load_permissions()
        assert mock_cache.get.call_count == 2


class TestTemplatePermissionsEdgeCases:
    """Edge case tests for TemplatePermissions."""

    def test_empty_field_permissions_list(self):
        """Test handling of empty field_permissions list."""
        mock_cache = make_mock_cache(
            {
                "SomeCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        # Field not in empty list, inherits from command
        assert tested.can_edit_field("SomeCommand", "any_field") is True
        assert tested.get_add_instructions("SomeCommand", "any_field") == []
        assert tested.get_editable_fields("SomeCommand") == set()

    def test_missing_field_permissions_key(self):
        """Test handling when field_permissions key is missing."""
        mock_cache = make_mock_cache(
            {
                "SomeCommand": {
                    "plugin_can_edit": True,
                    # No field_permissions key
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        # Should default to empty list for field_permissions
        assert tested.can_edit_field("SomeCommand", "any_field") is True
        assert tested.get_add_instructions("SomeCommand", "any_field") == []

    def test_field_permission_without_field_name(self):
        """Test handling of field permission entry without field_name."""
        mock_cache = make_mock_cache(
            {
                "SomeCommand": {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {"plugin_can_edit": True}  # Missing field_name
                    ],
                }
            }
        )

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        # Should not match any field
        assert tested.can_edit_field("SomeCommand", "narrative") is True
        assert tested.get_add_instructions("SomeCommand", "narrative") == []

    def test_multiple_notes_separate_caches(self):
        """Test that different note UUIDs have separate caches."""
        mock_cache1 = make_mock_cache({"CommandA": {"plugin_can_edit": True}})
        mock_cache2 = make_mock_cache({"CommandB": {"plugin_can_edit": False}})

        tested1 = TemplatePermissions("note-uuid-1", cache_getter=make_cache_getter(mock_cache1))
        tested2 = TemplatePermissions("note-uuid-2", cache_getter=make_cache_getter(mock_cache2))

        result1 = tested1._load_permissions()
        result2 = tested2._load_permissions()

        assert result1 == {"CommandA": {"plugin_can_edit": True}}
        assert result2 == {"CommandB": {"plugin_can_edit": False}}

    def test_command_type_not_in_permissions(self):
        """Test behavior when command type is not in permissions dict."""
        mock_cache = make_mock_cache({"SomeOtherCommand": {"plugin_can_edit": True}})

        tested = TemplatePermissions("test-note-uuid", cache_getter=make_cache_getter(mock_cache))
        # Command not in permissions, should allow all operations
        assert tested.can_edit_command("NotInPermissionsCommand") is True
        assert tested.can_edit_field("NotInPermissionsCommand", "any_field") is True
        assert tested.get_add_instructions("NotInPermissionsCommand", "any_field") == []
        assert tested.get_editable_fields("NotInPermissionsCommand") is None


class TestDefaultCacheGetter:
    """Tests for the _default_cache_getter function."""

    def test_default_cache_getter_with_sdk_available(self):
        """Test _default_cache_getter when canvas_sdk is available."""
        from hyperscribe.libraries import template_permissions

        # Save original value
        original_get_cache = template_permissions._get_cache

        try:
            # Mock _get_cache to be available
            mock_cache = MagicMock()
            template_permissions._get_cache = MagicMock(return_value=mock_cache)

            result = template_permissions._default_cache_getter()
            assert result == mock_cache
            template_permissions._get_cache.assert_called_once()
        finally:
            # Restore original value
            template_permissions._get_cache = original_get_cache

    def test_default_cache_getter_with_sdk_unavailable(self):
        """Test _default_cache_getter raises ImportError when canvas_sdk unavailable."""
        from hyperscribe.libraries import template_permissions

        # Save original value
        original_get_cache = template_permissions._get_cache

        try:
            # Set _get_cache to None to simulate missing SDK
            template_permissions._get_cache = None

            with pytest.raises(ImportError) as exc_info:
                template_permissions._default_cache_getter()

            assert "canvas_sdk.caching.plugins not available" in str(exc_info.value)
        finally:
            # Restore original value
            template_permissions._get_cache = original_get_cache

    def test_template_permissions_uses_default_cache_getter(self):
        """Test TemplatePermissions uses default cache getter when not provided."""
        from hyperscribe.libraries import template_permissions

        # Save original values
        original_get_cache = template_permissions._get_cache
        original_default_getter = template_permissions._default_cache_getter

        try:
            # Mock the default getter
            mock_cache = MagicMock()
            mock_cache.get.return_value = {"TestCommand": {"plugin_can_edit": True}}
            template_permissions._get_cache = MagicMock(return_value=mock_cache)

            # Create instance without cache_getter
            tested = TemplatePermissions("test-note-uuid")

            # Access permissions which should use default getter
            result = tested._load_permissions()

            assert result == {"TestCommand": {"plugin_can_edit": True}}
        finally:
            # Restore original values
            template_permissions._get_cache = original_get_cache
