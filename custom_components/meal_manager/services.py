"""Actions of the Meal Manager integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import CONF_SHOPPING_LIST, DOMAIN
from .core.planner import MAX_DAYS, MealPlanner, PlannerError

ATTR_MEAL_ID = "meal_id"
ATTR_SLOT = "slot"
ATTR_DATE = "date"
ATTR_COOKED = "cooked"
ATTR_TITLE = "title"
ATTR_START_DATE = "start_date"
ATTR_DAYS = "days"
ATTR_DRAFT = "draft"
ATTR_ENTITY_ID = "entity_id"

SCHEMA_GENERATE = vol.Schema(
    {
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_DAYS): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_DAYS)),
    }
)
SCHEMA_EMPTY = vol.Schema({})
SCHEMA_MARK_COOKED = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_MEAL_ID): cv.string,
            vol.Optional(ATTR_SLOT): cv.string,
            vol.Optional(ATTR_DATE): cv.date,
            vol.Optional(ATTR_COOKED, default=True): cv.boolean,
        }
    ),
    cv.has_at_least_one_key(ATTR_MEAL_ID, ATTR_SLOT),
)
SCHEMA_MEAL = vol.Schema({vol.Required(ATTR_MEAL_ID): cv.string})
SCHEMA_BAN = vol.All(
    vol.Schema({vol.Optional(ATTR_MEAL_ID): cv.string, vol.Optional(ATTR_TITLE): cv.string}),
    cv.has_at_least_one_key(ATTR_MEAL_ID, ATTR_TITLE),
)
SCHEMA_UNBAN = vol.Schema({vol.Required(ATTR_TITLE): cv.string})
SCHEMA_SHOPPING = vol.Schema(
    {
        vol.Optional(ATTR_DRAFT, default=False): cv.boolean,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


def _planner(hass: HomeAssistant) -> MealPlanner:
    from . import loaded_data  # noqa: PLC0415 - avoid import cycle

    data = loaded_data(hass)
    if data is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    return data.planner


async def _generate(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    plan = await _planner(hass).generate_draft(call.data.get(ATTR_START_DATE), call.data.get(ATTR_DAYS))
    return {"plan_id": plan.id, "meals": len(plan.meals)}


async def _accept(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    await _planner(hass).accept_draft()
    return None


async def _discard(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    await _planner(hass).discard_draft()
    return None


async def _mark_cooked(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    planner = _planner(hass)
    meal_id = call.data.get(ATTR_MEAL_ID)
    if not meal_id:
        day = call.data.get(ATTR_DATE) or dt_util.now().date()
        meal_id = planner.find_slot(day, call.data[ATTR_SLOT]).id
    await planner.mark_cooked(meal_id, call.data[ATTR_COOKED])
    return None


async def _decline(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    meal = await _planner(hass).decline_meal(call.data[ATTR_MEAL_ID])
    return {"meal_id": meal.id, "title": meal.recipe.title}


async def _ban(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    ban = await _planner(hass).ban_meal(call.data.get(ATTR_MEAL_ID), call.data.get(ATTR_TITLE))
    return {"title": ban.title}


async def _unban(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    await _planner(hass).unban(call.data[ATTR_TITLE])
    return None


async def _shopping_list(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    from . import loaded_data  # noqa: PLC0415

    planner = _planner(hass)
    items = [i.display() for i in planner.shopping_list(draft=call.data[ATTR_DRAFT])]
    data = loaded_data(hass)
    target = call.data.get(ATTR_ENTITY_ID) or (data.general.get(CONF_SHOPPING_LIST) if data else None)
    if target:
        for item in items:
            await hass.services.async_call(
                "todo", "add_item", {"item": item}, target={"entity_id": target}, blocking=True
            )
    return {"items": items, "entity_id": target}


Handler = Callable[[HomeAssistant, ServiceCall], Awaitable[ServiceResponse]]

SERVICES: dict[str, tuple[Handler, vol.Schema, SupportsResponse]] = {
    "generate_plan": (_generate, SCHEMA_GENERATE, SupportsResponse.OPTIONAL),
    "accept_plan": (_accept, SCHEMA_EMPTY, SupportsResponse.NONE),
    "discard_plan": (_discard, SCHEMA_EMPTY, SupportsResponse.NONE),
    "mark_cooked": (_mark_cooked, SCHEMA_MARK_COOKED, SupportsResponse.NONE),
    "decline_meal": (_decline, SCHEMA_MEAL, SupportsResponse.OPTIONAL),
    "ban_meal": (_ban, SCHEMA_BAN, SupportsResponse.OPTIONAL),
    "unban_meal": (_unban, SCHEMA_UNBAN, SupportsResponse.NONE),
    "add_to_shopping_list": (_shopping_list, SCHEMA_SHOPPING, SupportsResponse.OPTIONAL),
}


def async_setup(hass: HomeAssistant) -> None:
    """Register the actions."""
    for name, (func, schema, response) in SERVICES.items():
        hass.services.async_register(
            DOMAIN, name, _bind(hass, func), schema=schema, supports_response=response
        )


def _bind(hass: HomeAssistant, func: Handler) -> Callable[[ServiceCall], Awaitable[ServiceResponse]]:
    """Bind a handler to hass and translate planner errors."""

    async def handler(call: ServiceCall) -> ServiceResponse:
        try:
            return await func(hass, call)
        except PlannerError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=err.code,
                translation_placeholders=err.placeholders,
            ) from err

    return handler
