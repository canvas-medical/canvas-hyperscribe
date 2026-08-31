import json

from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons

from hyperscribe.scribe.command_buttons import command_button_hiding_enabled, configure_command_buttons_effect


def test_configure_command_buttons_effect_covers_all_locations() -> None:
    effect = configure_command_buttons_effect(42, ConfigureCommandButtons.Visibility.HIDDEN)

    assert effect.type == ConfigureCommandButtons.Meta.effect_type
    payload = json.loads(effect.payload)["data"]
    # patient_id is coerced to a string.
    assert payload["patient_id"] == "42"
    # One config per Location, all at the requested visibility.
    locations = payload["locations"]
    assert {loc["location"] for loc in locations} == {loc.value for loc in ConfigureCommandButtons.Location}
    assert all(loc["visibility"] == ConfigureCommandButtons.Visibility.HIDDEN for loc in locations)


def test_configure_command_buttons_effect_visible() -> None:
    effect = configure_command_buttons_effect("patient-uuid", ConfigureCommandButtons.Visibility.VISIBLE)
    payload = json.loads(effect.payload)["data"]
    assert payload["patient_id"] == "patient-uuid"
    assert all(loc["visibility"] == ConfigureCommandButtons.Visibility.VISIBLE for loc in payload["locations"])


def test_command_button_hiding_enabled_when_secret_is_true() -> None:
    for value in ("true", "True", "TRUE", " true "):
        assert command_button_hiding_enabled({"ScribeHideChartButtons": value}) is True


def test_command_button_hiding_disabled_by_default() -> None:
    # Unset is the shipping state: the buttons are never hidden.
    assert command_button_hiding_enabled({}) is False


def test_command_button_hiding_rejects_other_truthy_values() -> None:
    # Strict "true" match, so the secret can be set to "false" to disable rather
    # than having to be deleted, and a stray value can't switch the feature on.
    for value in ("", "false", "False", "1", "y", "yes", "on"):
        assert command_button_hiding_enabled({"ScribeHideChartButtons": value}) is False
