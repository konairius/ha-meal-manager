"""Settings resolution."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.meal_manager.core.settings import (
    Override,
    PlannerSettings,
    Setting,
    SettingsResolver,
    ValueSource,
    parse_value,
)

SATURDAY = date(2026, 10, 10)
MONDAY = date(2026, 10, 12)


def resolver(settings: PlannerSettings, states: dict | None = None) -> SettingsResolver:
    states = states or {}
    return SettingsResolver(settings, lambda entity, attr: states.get((entity, attr)))


def test_built_in_defaults() -> None:
    r = resolver(PlannerSettings())
    assert r.resolve(Setting.PORTIONS, MONDAY, "dinner").value == 2
    assert r.resolve(Setting.CALORIES, MONDAY).value is None
    assert [s.name for s in r.slots_for(MONDAY)] == ["breakfast", "lunch", "dinner"]


def test_layer_order() -> None:
    settings = PlannerSettings(
        defaults={Setting.EFFORT: ValueSource(value=2)},
        overrides=[
            Override(Setting.EFFORT, ValueSource(value=3), weekday=5),
            Override(Setting.EFFORT, ValueSource(value="low"), slot="breakfast"),
            Override(Setting.EFFORT, ValueSource(value=2), weekday=5, slot="breakfast"),
        ],
    )
    r = resolver(settings)
    assert r.resolve(Setting.EFFORT, SATURDAY, "dinner").value == 3
    assert r.resolve(Setting.EFFORT, MONDAY, "breakfast").value == 1
    sat_breakfast = r.resolve(Setting.EFFORT, SATURDAY, "breakfast")
    assert sat_breakfast.value == 2
    assert sat_breakfast.origin == "sat+breakfast"
    assert r.resolve(Setting.EFFORT, MONDAY, "dinner").origin == "default"


def test_entity_with_fallback() -> None:
    settings = PlannerSettings(
        defaults={
            Setting.CALORIES: ValueSource(value=2000, entity_id="sensor.kcal"),
            Setting.PORTIONS: ValueSource(entity_id="zone.home"),
            Setting.HEALTH: ValueSource(entity_id="sensor.fit", attribute="health"),
        }
    )
    states = {("sensor.kcal", None): "2450.6", ("zone.home", None): "3", ("sensor.fit", "health"): 4}
    r = resolver(settings, states)
    assert r.resolve(Setting.CALORIES, MONDAY).value == 2451
    assert r.resolve(Setting.CALORIES, MONDAY).origin == "default:sensor.kcal"
    assert r.resolve(Setting.PORTIONS, MONDAY, "lunch").value == 3
    assert r.resolve(Setting.HEALTH, MONDAY, "lunch").value == 4

    flaky = resolver(settings, {("sensor.kcal", None): "unavailable", ("zone.home", None): "0"})
    assert flaky.resolve(Setting.CALORIES, MONDAY).value == 2000
    assert flaky.resolve(Setting.CALORIES, MONDAY).origin == "default"
    assert flaky.resolve(Setting.PORTIONS, MONDAY, "lunch").origin == "built-in"


def test_day_scoped_ignores_meal_layers() -> None:
    settings = PlannerSettings(
        overrides=[
            Override(Setting.MEALS_PER_DAY, ValueSource(value=2), weekday=5),
            Override(Setting.CALORIES, ValueSource(value=1500), slot="dinner"),
        ]
    )
    r = resolver(settings)
    assert [s.name for s in r.slots_for(SATURDAY)] == ["lunch", "dinner"]
    assert r.resolve(Setting.CALORIES, MONDAY, "dinner").value is None


def test_calorie_split() -> None:
    r = resolver(PlannerSettings(defaults={Setting.CALORIES: ValueSource(value=2000)}))
    slots = r.slots_for(MONDAY)
    targets = r.kcal_targets(MONDAY, slots)
    assert targets == {"breakfast": 526, "lunch": 737, "dinner": 737}


@pytest.mark.parametrize(
    ("setting", "raw", "expected"),
    [
        (Setting.EFFORT, "High", 3),
        (Setting.EFFORT, "4", None),
        (Setting.HEALTH, "4,6", 5),
        (Setting.HEALTH, 9, None),
        (Setting.CALORIES, 0, "none"),
        (Setting.PORTIONS, "abc", None),
        (Setting.PORTIONS, True, None),
    ],
)
def test_parse(setting: Setting, raw, expected) -> None:
    value = parse_value(setting, raw)
    if expected is None:
        assert value is not None and not isinstance(value, int | type(None))
    elif expected == "none":
        assert value is None
    else:
        assert value == expected


def test_round_trip() -> None:
    settings = PlannerSettings(
        defaults={Setting.CALORIES: ValueSource(value=2000, entity_id="sensor.kcal")},
        overrides=[Override(Setting.PORTIONS, ValueSource(value=4), weekday=6, slot="dinner")],
    )
    assert PlannerSettings.from_dict(settings.to_dict()) == settings
