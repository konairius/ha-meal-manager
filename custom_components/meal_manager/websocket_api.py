"""Websocket API used by the card and panel: one live subscription with the full view."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import SIGNAL_UPDATE
from .core.models import Plan, PlannedMeal, nice_quantity
from .core.settings import Setting, SettingsResolver

PREVIEW_DAYS = 7


def async_setup(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe)


def meal_view(meal: PlannedMeal, resolver: SettingsResolver) -> dict[str, Any]:
    slot = resolver.settings.slot(meal.slot)
    recipe = meal.recipe
    return {
        "id": meal.id,
        "day": meal.day.isoformat(),
        "slot": meal.slot,
        "time": slot.time if slot else None,
        "title": recipe.title,
        "minutes": recipe.minutes,
        "effort": recipe.effort,
        "health": recipe.health,
        "tags": list(recipe.tags),
        "source": recipe.source,
        "portions": meal.portions,
        "kcal": meal.kcal_per_person,
        "kcal_target": meal.kcal_target,
        "scale": meal.scale,
        "ingredients": [
            {**i.to_dict(), "quantity": nice_quantity(i.quantity)} for i in meal.scaled_ingredients()
        ],
        "steps": list(recipe.steps),
        "cooked": meal.cooked,
    }


def plan_view(plan: Plan | None, resolver: SettingsResolver) -> dict[str, Any] | None:
    if plan is None:
        return None
    order = {s.name: s.time for s in resolver.settings.slots}
    meals = sorted(plan.meals, key=lambda m: (m.day, order.get(m.slot, "99:99")))
    return {
        "id": plan.id,
        "status": str(plan.status),
        "start": plan.start.isoformat(),
        "days": plan.days,
        "cooked": plan.cooked_count,
        "total": len(plan.meals),
        "meals": [meal_view(m, resolver) for m in meals],
    }


def settings_preview(resolver: SettingsResolver) -> list[dict[str, Any]]:
    """Resolved settings for the next days, with the layer each value came from."""
    today = dt_util.now().date()
    preview = []
    for offset in range(PREVIEW_DAYS):
        day = today + timedelta(days=offset)
        slots = resolver.slots_for(day)
        targets = resolver.kcal_targets(day, slots)
        calories = resolver.resolve(Setting.CALORIES, day)
        meals_per_day = resolver.resolve(Setting.MEALS_PER_DAY, day)
        preview.append(
            {
                "day": day.isoformat(),
                "calories": {"value": calories.value, "origin": calories.origin},
                "meals_per_day": {"value": meals_per_day.value, "origin": meals_per_day.origin},
                "meals": [
                    {
                        "slot": slot.name,
                        "kcal_target": targets[slot.name],
                        **{
                            str(setting): {
                                "value": (r := resolver.resolve(setting, day, slot.name)).value,
                                "origin": r.origin,
                            }
                            for setting in (Setting.PORTIONS, Setting.EFFORT, Setting.HEALTH)
                        },
                    }
                    for slot in slots
                ],
            }
        )
    return preview


def build_view(hass: HomeAssistant) -> dict[str, Any]:
    from . import loaded_data  # noqa: PLC0415 - avoid import cycle

    data = loaded_data(hass)
    if data is None:
        return {"loaded": False}
    resolver = data.resolver()
    planner = data.planner
    state = planner.state
    return {
        "loaded": True,
        "today": dt_util.now().date().isoformat(),
        "generating": planner.generating,
        "default_days": planner.options.default_days,
        "active": plan_view(state.active, resolver),
        "draft": plan_view(state.draft, resolver),
        "bans": [b.to_dict() for b in sorted(state.bans, key=lambda b: b.key)],
        "slots": [s.to_dict() for s in resolver.settings.slots],
        "preview": settings_preview(resolver),
        "recipes": data.catalog.count(),
    }


@websocket_api.websocket_command({vol.Required("type"): "meal_manager/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the current view and every change after it."""

    @callback
    def send() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], build_view(hass)))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATE, send)
    connection.send_result(msg["id"])
    send()
