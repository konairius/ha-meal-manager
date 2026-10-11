"""Meal Manager: local meal planning for Home Assistant (composition root)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import services, websocket_api
from .adapters import AiTaskRecipeSource, HaEventSink, HaStateStore, load_recipes, state_reader
from .const import (
    CARD_FILE,
    CONF_AI_TASK_ENTITY,
    CONF_AUTO_NEW_PLAN,
    CONF_AVOID_RECENT,
    CONF_DEFAULT_DAYS,
    CONF_PREFERENCES,
    CONF_SEASON,
    CONF_SHOW_PANEL,
    DEFAULT_GENERAL,
    DOMAIN,
    OPT_GENERAL,
    PANEL_URL_PATH,
    SIGNAL_UPDATE,
    URL_BASE,
    VERSION,
)
from .core.catalog import RecipeCatalog
from .core.models import SeasonMode
from .core.planner import MealPlanner, PlannerOptions
from .core.ports import RecipeSource
from .core.settings import PlannerSettings, SettingsResolver
from .core.sources import FallbackSource

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class MealManagerData:
    """Runtime objects of a config entry."""

    planner: MealPlanner
    catalog: RecipeCatalog
    general: dict
    resolver: Callable[[], SettingsResolver]


type MealManagerConfigEntry = ConfigEntry[MealManagerData]


def general_options(entry: ConfigEntry) -> dict:
    return {**DEFAULT_GENERAL, **entry.options.get(OPT_GENERAL, {})}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register frontend resources, websocket commands and actions."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(Path(__file__).parent / "frontend"), cache_headers=False)]
    )
    frontend.add_extra_js_url(hass, f"{URL_BASE}/{CARD_FILE}?v={VERSION}")
    websocket_api.async_setup(hass)
    services.async_setup(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MealManagerConfigEntry) -> bool:
    general = general_options(entry)
    recipes = await hass.async_add_executor_job(load_recipes, hass.config.config_dir)
    catalog = RecipeCatalog(recipes)
    source: RecipeSource = catalog
    if general[CONF_AI_TASK_ENTITY]:
        source = FallbackSource(
            AiTaskRecipeSource(hass, general[CONF_AI_TASK_ENTITY], general[CONF_PREFERENCES]),
            catalog,
        )

    read_state = state_reader(hass)

    def resolver() -> SettingsResolver:
        return SettingsResolver(PlannerSettings.from_dict(entry.options), read_state)

    planner = MealPlanner(
        store=HaStateStore(hass),
        source=source,
        resolver=resolver,
        events=HaEventSink(hass),
        clock=dt_util.now,
        options=PlannerOptions(
            default_days=int(general[CONF_DEFAULT_DAYS]),
            avoid_recent=int(general[CONF_AVOID_RECENT]),
            auto_new_plan=bool(general[CONF_AUTO_NEW_PLAN]),
            season=SeasonMode(general[CONF_SEASON]),
        ),
    )
    await planner.async_load()
    entry.runtime_data = MealManagerData(planner=planner, catalog=catalog, general=general, resolver=resolver)

    @callback
    def _changed() -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    entry.async_on_unload(planner.add_listener(_changed))
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    if general[CONF_SHOW_PANEL]:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="meal-manager-panel",
            sidebar_title="Meal plan",
            sidebar_icon="mdi:silverware-fork-knife",
            module_url=f"{URL_BASE}/{CARD_FILE}?v={VERSION}",
            require_admin=False,
            config={},
        )
        entry.async_on_unload(lambda: frontend.async_remove_panel(hass, PANEL_URL_PATH))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _changed()  # refresh open cards after a reload
    return True


async def _async_reload(hass: HomeAssistant, entry: MealManagerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MealManagerConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def loaded_data(hass: HomeAssistant) -> MealManagerData | None:
    """Runtime data of the (single) loaded entry."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None
