"""Planning settings and their layered resolution.

Every setting can be a fixed value, an entity (state or attribute) or both, in which case
the fixed value is the fallback when the entity is unavailable or unparsable. Values are
resolved from the most specific layer to the least specific one:

    weekday + meal  >  meal  >  weekday  >  default  >  built-in

Day-scoped settings (calories, meals per day) only use the weekday and default layers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from .models import MealType

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

UNAVAILABLE_STATES = {"unavailable", "unknown", "none", ""}


class Setting(StrEnum):
    """Configurable planning settings."""

    PORTIONS = "portions"
    EFFORT = "effort"
    HEALTH = "health"
    CALORIES = "calories"
    MEALS_PER_DAY = "meals_per_day"


DAY_SCOPED = frozenset({Setting.CALORIES, Setting.MEALS_PER_DAY})

BUILT_IN: dict[Setting, Any] = {
    Setting.PORTIONS: 2,
    Setting.EFFORT: 2,
    Setting.HEALTH: 3,
    Setting.CALORIES: None,
    Setting.MEALS_PER_DAY: 3,
}

_EFFORT_WORDS = {
    "low": 1,
    "quick": 1,
    "easy": 1,
    "medium": 2,
    "normal": 2,
    "high": 3,
    "elaborate": 3,
}

_INVALID = object()


def _as_number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    try:
        return float(str(raw).strip().replace(",", "."))
    except ValueError:
        return None


def parse_value(setting: Setting, raw: Any) -> Any:
    """Parse a raw value for a setting. Returns ``_INVALID`` when it cannot be used."""
    if raw is None or (isinstance(raw, str) and raw.strip().casefold() in UNAVAILABLE_STATES):
        return _INVALID
    if setting is Setting.EFFORT:
        word = str(raw).strip().casefold()
        if word in _EFFORT_WORDS:
            return _EFFORT_WORDS[word]
        number = _as_number(raw)
        return round(number) if number is not None and 1 <= round(number) <= 3 else _INVALID
    number = _as_number(raw)
    if number is None:
        return _INVALID
    if setting is Setting.CALORIES:
        if number < 0:
            return _INVALID
        return None if number == 0 else round(number)
    value = round(number)
    if setting is Setting.HEALTH:
        return value if 1 <= value <= 5 else _INVALID
    if setting is Setting.PORTIONS:
        return value if value >= 1 else _INVALID
    if setting is Setting.MEALS_PER_DAY:
        return value if value >= 1 else _INVALID
    return _INVALID


def is_valid(setting: Setting, raw: Any) -> bool:
    return parse_value(setting, raw) is not _INVALID


@dataclass(frozen=True, slots=True)
class ValueSource:
    """A fixed value, an entity, or an entity with a fixed fallback value."""

    value: Any = None
    entity_id: str | None = None
    attribute: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.value in (None, "") and not self.entity_id

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.value not in (None, ""):
            data["value"] = self.value
        if self.entity_id:
            data["entity_id"] = self.entity_id
        if self.attribute:
            data["attribute"] = self.attribute
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ValueSource:
        data = data or {}
        return cls(
            value=data.get("value"),
            entity_id=data.get("entity_id") or None,
            attribute=data.get("attribute") or None,
        )


@dataclass(frozen=True, slots=True)
class Override:
    """A setting value that applies on a weekday, for a meal slot, or both."""

    setting: Setting
    source: ValueSource
    weekday: int | None = None  # 0 = Monday
    slot: str | None = None

    @property
    def key(self) -> str:
        day = WEEKDAYS[self.weekday] if self.weekday is not None else "*"
        return f"{self.setting}:{day}:{self.slot or '*'}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "setting": str(self.setting),
            "weekday": self.weekday,
            "slot": self.slot,
            **self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Override:
        weekday = data.get("weekday")
        return cls(
            setting=Setting(data["setting"]),
            source=ValueSource.from_dict(data),
            weekday=int(weekday) if weekday is not None else None,
            slot=data.get("slot") or None,
        )


@dataclass(frozen=True, slots=True)
class MealSlot:
    """A meal of the day."""

    name: str
    meal_type: MealType
    time: str  # HH:MM
    share: float  # relative share of the daily calories
    priority: int  # lower = kept first when there are fewer meals per day

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "meal_type": str(self.meal_type),
            "time": self.time,
            "share": self.share,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MealSlot:
        return cls(
            name=str(data["name"]),
            meal_type=MealType(data.get("meal_type", data["name"])),
            time=str(data["time"])[:5],
            share=float(data["share"]),
            priority=int(data["priority"]),
        )


DEFAULT_SLOTS: tuple[MealSlot, ...] = (
    MealSlot("breakfast", MealType.BREAKFAST, "07:30", 25, 3),
    MealSlot("lunch", MealType.LUNCH, "12:30", 35, 2),
    MealSlot("dinner", MealType.DINNER, "18:30", 35, 1),
    MealSlot("snack", MealType.SNACK, "15:30", 10, 4),
)


@dataclass(slots=True)
class PlannerSettings:
    """All planning settings."""

    defaults: dict[Setting, ValueSource] = field(default_factory=dict)
    overrides: list[Override] = field(default_factory=list)
    slots: tuple[MealSlot, ...] = DEFAULT_SLOTS

    def slot(self, name: str) -> MealSlot | None:
        return next((s for s in self.slots if s.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "defaults": {str(k): v.to_dict() for k, v in self.defaults.items()},
            "overrides": [o.to_dict() for o in self.overrides],
            "slots": [s.to_dict() for s in self.slots],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlannerSettings:
        data = data or {}
        slots = tuple(MealSlot.from_dict(s) for s in data.get("slots", ())) or DEFAULT_SLOTS
        return cls(
            defaults={Setting(k): ValueSource.from_dict(v) for k, v in data.get("defaults", {}).items()},
            overrides=[Override.from_dict(o) for o in data.get("overrides", ())],
            slots=slots,
        )


StateReader = Callable[[str, str | None], Any]
"""Returns the raw state (attribute is None) or attribute value of an entity, or None."""


@dataclass(frozen=True, slots=True)
class Resolved:
    """A resolved setting value and the layer it came from."""

    value: Any
    origin: str  # e.g. "default", "entity:sensor.x", "override:sat:dinner", "built-in"


class SettingsResolver:
    """Resolves settings for a day and slot."""

    def __init__(self, settings: PlannerSettings, read_state: StateReader) -> None:
        self._settings = settings
        self._read_state = read_state

    @property
    def settings(self) -> PlannerSettings:
        return self._settings

    def resolve(self, setting: Setting, day: date, slot: str | None = None) -> Resolved:
        for label, source in self._layers(setting, day.weekday(), slot):
            result = self._from_source(setting, source)
            if result is not None:
                value, from_entity = result
                origin = f"{label}:{source.entity_id}" if from_entity else label
                return Resolved(value, origin)
        return Resolved(BUILT_IN[setting], "built-in")

    def _layers(self, setting: Setting, weekday: int, slot: str | None) -> list[tuple[str, ValueSource]]:
        if setting in DAY_SCOPED:
            slot = None
        by_scope = {(o.weekday, o.slot): o.source for o in self._settings.overrides if o.setting is setting}
        candidates: list[tuple[str, tuple[int | None, str | None]]] = []
        if slot is not None:
            candidates.append((f"{WEEKDAYS[weekday]}+{slot}", (weekday, slot)))
            candidates.append((slot, (None, slot)))
        candidates.append((WEEKDAYS[weekday], (weekday, None)))
        layers = [(label, by_scope[scope]) for label, scope in candidates if scope in by_scope]
        if setting in self._settings.defaults:
            layers.append(("default", self._settings.defaults[setting]))
        return layers

    def _from_source(self, setting: Setting, source: ValueSource) -> tuple[Any, bool] | None:
        if source.entity_id:
            value = parse_value(setting, self._read_state(source.entity_id, source.attribute))
            if value is not _INVALID:
                return value, True
        if source.value not in (None, ""):
            value = parse_value(setting, source.value)
            if value is not _INVALID:
                return value, False
        return None

    def slots_for(self, day: date) -> list[MealSlot]:
        """The meal slots of a day, ordered by time."""
        count = self.resolve(Setting.MEALS_PER_DAY, day).value
        chosen = sorted(self._settings.slots, key=lambda s: (s.priority, s.time))[:count]
        return sorted(chosen, key=lambda s: s.time)

    def kcal_targets(self, day: date, slots: list[MealSlot]) -> dict[str, int | None]:
        """Split the daily calorie need (per person) across the day's slots."""
        daily = self.resolve(Setting.CALORIES, day).value
        total_share = sum(s.share for s in slots)
        if not daily or total_share <= 0:
            return {s.name: None for s in slots}
        return {s.name: round(daily * s.share / total_share) for s in slots}
