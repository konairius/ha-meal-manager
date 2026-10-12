"""Home Assistant implementations of the core ports."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store
import voluptuous as vol

from .const import DOMAIN, EVENT_PREFIX, USER_RECIPES_FILE
from .core.catalog import parse_recipes
from .core.llm import build_instructions, parse_recipe
from .core.models import MealRequest, Recipe
from .core.shopping import IngredientInfo, Package, ShoppingItem

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
BUILTIN_RECIPES = Path(__file__).parent / "data" / "recipes.json"
BUILTIN_INGREDIENTS = Path(__file__).parent / "data" / "ingredients.json"
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


def load_recipes(config_dir: str) -> list[Recipe]:
    """Load built-in recipes plus optional user recipes (blocking, run in executor)."""
    recipes: list[Recipe] = []
    sources = [(BUILTIN_RECIPES, "builtin"), (Path(config_dir) / USER_RECIPES_FILE, "user")]
    for path, name in sources:
        if not path.is_file():
            continue
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            _LOGGER.error("Cannot read recipes from %s: %s", path, err)
            continue
        parsed, errors = parse_recipes(items if isinstance(items, list) else [], name)
        for error in errors:
            _LOGGER.warning("Skipping invalid recipe in %s: %s", path, error)
        recipes.extend(parsed)
    return recipes


def load_ingredients() -> dict[str, IngredientInfo]:
    """Translations and supermarket sections of known ingredients (blocking, run in executor)."""
    raw = json.loads(BUILTIN_INGREDIENTS.read_text(encoding="utf-8"))

    def package(data: dict[str, Any] | None) -> Package | None:
        if not data:
            return None
        return Package(float(data["size"]), data["unit"], {"en": data["en"], "de": data["de"]})

    return {
        name: IngredientInfo(
            category=data.get("category", "other"),
            names={"en": name, "de": data.get("de", name)},
            package=package(data.get("pack")),
        )
        for name, data in raw.items()
    }


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


async def generate_data(hass: HomeAssistant, **kwargs: Any) -> Any:
    """Run an AI Task data generation (the integration is only imported when used)."""
    from homeassistant.components import ai_task  # noqa: PLC0415 - optional dependency

    return await ai_task.async_generate_data(hass, **kwargs)


class AiTaskRecipeSource:
    """Asks a local model through Home Assistant's AI Task integration."""

    def __init__(self, hass: HomeAssistant, entity_id: str | None, preferences: str) -> None:
        self._hass = hass
        self._entity_id = entity_id
        self._preferences = preferences

    async def suggest(self, request: MealRequest) -> Recipe | None:
        instructions = build_instructions(request, self._preferences)
        for _ in range(AI_ATTEMPTS):
            try:
                result = await generate_data(
                    self._hass,
                    task_name="Meal Manager",
                    entity_id=self._entity_id,
                    instructions=instructions,
                    structure=AI_STRUCTURE,
                )
            except (HomeAssistantError, KeyError) as err:
                _LOGGER.warning("AI Task generation failed: %s", err)
                return None
            recipe = parse_recipe(result.data, request)
            if recipe is not None:
                return recipe
        return None
