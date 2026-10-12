"""Home Assistant implementations of the core ports."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store
import voluptuous as vol

from .const import DOMAIN, EVENT_PREFIX
from .core.llm import Rejected, build_instructions, parse_recipe, retry_instructions
from .core.models import Ingredient, MealRequest, Recipe
from .core.shopping import ShoppingItem, build_shopping_instructions, parse_shopping_list

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
AI_ATTEMPTS = 3


class HaStateStore:
    """Planner state in ``.storage/meal_manager``."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, DOMAIN)

    async def load(self) -> dict[str, Any] | None:
        return await self._store.async_load()

    async def save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)


class HaEventSink:
    """Fires planner events on the Home Assistant event bus as ``meal_manager_<event>``."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    def publish(self, event: str, data: dict[str, Any]) -> None:
        self._hass.bus.async_fire(f"{EVENT_PREFIX}{event}", data)


def state_reader(hass: HomeAssistant):
    """Read an entity's state or attribute for settings resolution."""

    def read(entity_id: str, attribute: str | None) -> Any:
        state = hass.states.get(entity_id)
        if state is None:
            return None
        return state.attributes.get(attribute) if attribute else state.state

    return read


class HaTodoShoppingList:
    """Writes the shopping list to a to-do entity, replacing what it wrote last time.

    Open items this integration added before are removed first, so pressing the button twice or
    after a change of plan does not duplicate anything. Items the household added itself, and
    items already ticked off, are left alone.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.shopping")

    async def replace(self, entity_id: str, items: list[ShoppingItem]) -> None:
        stored = await self._store.async_load() or {}
        previous = set(stored.get(entity_id, []))
        response = await self._hass.services.async_call(
            "todo",
            "get_items",
            {"status": ["needs_action"]},
            target={"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
        open_items = {i["summary"]: i["uid"] for i in (response or {}).get(entity_id, {}).get("items", [])}
        if stale := [uid for summary, uid in open_items.items() if summary in previous]:
            await self._hass.services.async_call(
                "todo", "remove_item", {"item": stale}, target={"entity_id": entity_id}, blocking=True
            )
        added: list[str] = []
        for item in items:
            summary = item.display()
            if summary in open_items and summary not in previous:
                continue  # the household already has exactly this on the list
            await self._hass.services.async_call(
                "todo", "add_item", {"item": summary}, target={"entity_id": entity_id}, blocking=True
            )
            added.append(summary)
        await self._store.async_save({**stored, entity_id: added})


AI_STRUCTURE = vol.Schema(
    {
        vol.Required("title"): selector.TextSelector(),
        vol.Required("minutes"): selector.NumberSelector(),
        vol.Required("kcal"): selector.NumberSelector(),
        vol.Required("health"): selector.NumberSelector(),
        vol.Required("ingredients"): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        vol.Required("steps"): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
    }
)


SHOPPING_STRUCTURE = vol.Schema(
    {vol.Required("items"): selector.TextSelector(selector.TextSelectorConfig(multiline=True))}
)


async def generate_data(hass: HomeAssistant, **kwargs: Any) -> Any:
    """Run an AI Task data generation (the integration is only imported when used)."""
    from homeassistant.components import ai_task  # noqa: PLC0415 - imported when used

    return await ai_task.async_generate_data(hass, **kwargs)


class AiTask:
    """Asks the local model through Home Assistant's AI Task integration and checks the answer.

    A rejected answer is asked for again, with the reason, up to AI_ATTEMPTS times.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str | None) -> None:
        self._hass = hass
        self._entity_id = entity_id  # None: the preferred AI Task entity

    async def ask[T](
        self, task_name: str, instructions: str, structure: vol.Schema, parse: Callable[[Any], T]
    ) -> T | None:
        prompt = instructions
        for _ in range(AI_ATTEMPTS):
            try:
                result = await generate_data(
                    self._hass,
                    task_name=task_name,
                    entity_id=self._entity_id,
                    instructions=prompt,
                    structure=structure,
                )
            except (HomeAssistantError, KeyError) as err:
                _LOGGER.warning("AI Task generation failed: %s", err)
                return None
            try:
                return parse(result.data)
            except Rejected as err:
                _LOGGER.info("%s: rejected the model's answer, asking again: %s", task_name, err)
                prompt = retry_instructions(instructions, str(err))
        _LOGGER.warning("%s: no usable answer from the model after %s attempts", task_name, AI_ATTEMPTS)
        return None


class AiTaskRecipeSource:
    """Every dish comes from the local model."""

    def __init__(self, ai: AiTask, preferences: str, language: str) -> None:
        self._ai = ai
        self._preferences = preferences
        self._language = language

    async def suggest(self, request: MealRequest) -> Recipe | None:
        instructions = build_instructions(request, self._preferences, self._language)
        return await self._ai.ask(
            "Meal Manager recipe", instructions, AI_STRUCTURE, lambda data: parse_recipe(data, request)
        )


class AiTaskShoppingList:
    """The model writes the shopping list from the summed ingredients."""

    def __init__(self, ai: AiTask) -> None:
        self._ai = ai

    async def create(
        self, ingredients: list[Ingredient], pantry: str, language: str
    ) -> list[ShoppingItem] | None:
        if not ingredients:
            return []
        instructions = build_shopping_instructions(ingredients, pantry, language)
        return await self._ai.ask(
            "Meal Manager shopping list",
            instructions,
            SHOPPING_STRUCTURE,
            lambda data: parse_shopping_list(data, ingredients),
        )
