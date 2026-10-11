"""Calendar with the meals of the active plan (and the draft, marked as such)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MealManagerConfigEntry
from .core.models import PlannedMeal
from .entity import MealManagerEntity

MEAL_DURATION = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealManagerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MealPlanCalendar(entry)])


class MealPlanCalendar(MealManagerEntity, CalendarEntity):
    """The active meal plan as calendar events."""

    def __init__(self, entry: MealManagerConfigEntry) -> None:
        super().__init__(entry, "meal_plan")

    def _events(self) -> list[CalendarEvent]:
        active = self.data.planner.state.active
        if active is None:
            return []
        settings = self.data.resolver().settings
        events = []
        for meal in active.meals:
            slot = settings.slot(meal.slot)
            hour, minute = (int(p) for p in (slot.time if slot else "12:00").split(":"))
            start = datetime.combine(meal.day, time(hour, minute), dt_util.get_default_time_zone())
            events.append(self._event(meal, start))
        return sorted(events, key=lambda e: e.start)

    @staticmethod
    def _event(meal: PlannedMeal, start: datetime) -> CalendarEvent:
        ingredients = "\n".join(f"- {i.display()}" for i in meal.scaled_ingredients())
        steps = "\n".join(f"{n}. {s}" for n, s in enumerate(meal.recipe.steps, 1))
        prefix = "✓ " if meal.cooked else ""
        return CalendarEvent(
            start=start,
            end=start + MEAL_DURATION,
            summary=f"{prefix}{meal.recipe.title}",
            description=f"{meal.portions} portions, ~{meal.kcal_per_person} kcal each, "
            f"{meal.recipe.minutes} min\n\n{ingredients}\n\n{steps}".strip(),
            uid=meal.id,
        )

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((e for e in self._events() if e.end > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [e for e in self._events() if e.end > start_date and e.start < end_date]
