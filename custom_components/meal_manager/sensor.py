"""Sensors: plan status, next meal and today's meal per slot."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MealManagerConfigEntry
from .core.models import PlannedMeal
from .entity import MealManagerEntity

STATUS_OPTIONS = ["none", "active", "completed"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealManagerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    slots = entry.runtime_data.resolver().settings.slots
    async_add_entities(
        [
            PlanStatusSensor(entry),
            NextMealSensor(entry),
            *(TodaySlotSensor(entry, slot.name) for slot in slots),
        ]
    )


def meal_attributes(meal: PlannedMeal | None) -> dict[str, Any]:
    if meal is None:
        return {}
    return {
        "meal_id": meal.id,
        "date": meal.day.isoformat(),
        "slot": meal.slot,
        "minutes": meal.recipe.minutes,
        "kcal": meal.kcal_per_person,
        "portions": meal.portions,
        "cooked": meal.cooked,
        "ingredients": [i.display() for i in meal.scaled_ingredients()],
        "steps": list(meal.recipe.steps),
    }


class PlanStatusSensor(MealManagerEntity, SensorEntity):
    """Status of the active plan."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_icon = "mdi:calendar-check"

    def __init__(self, entry: MealManagerConfigEntry) -> None:
        super().__init__(entry, "plan_status")

    @property
    def native_value(self) -> str:
        active = self.data.planner.state.active
        return str(active.status) if active else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.data.planner.state
        active = state.active
        return {
            "cooked": active.cooked_count if active else 0,
            "total": len(active.meals) if active else 0,
            "start": active.start.isoformat() if active else None,
            "days": active.days if active else 0,
            "draft_pending": state.draft is not None,
            "generating": self.data.planner.generating,
            "bans": [b.title for b in state.bans],
        }


class NextMealSensor(MealManagerEntity, SensorEntity):
    """Earliest uncooked meal of the active plan."""

    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, entry: MealManagerConfigEntry) -> None:
        super().__init__(entry, "next_meal")

    def _meal(self) -> PlannedMeal | None:
        return self.data.planner.next_meal(dt_util.now())

    @property
    def native_value(self) -> str | None:
        meal = self._meal()
        return meal.recipe.title if meal else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return meal_attributes(self._meal())


class TodaySlotSensor(MealManagerEntity, SensorEntity):
    """Today's meal in one slot."""

    _attr_icon = "mdi:food"

    def __init__(self, entry: MealManagerConfigEntry, slot: str) -> None:
        super().__init__(entry, f"today_{slot}")
        self._slot = slot

    def _meal(self) -> PlannedMeal | None:
        today = dt_util.now().date()
        return next((m for m in self.data.planner.meals_on(today) if m.slot == self._slot), None)

    @property
    def native_value(self) -> str | None:
        meal = self._meal()
        return meal.recipe.title if meal else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return meal_attributes(self._meal())
