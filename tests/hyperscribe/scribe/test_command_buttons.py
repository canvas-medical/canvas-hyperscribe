import json

from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons

from hyperscribe.scribe.command_buttons import configure_command_buttons_effect


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
