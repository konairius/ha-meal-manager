"""Constants of the Meal Manager integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "meal_manager"
VERSION: Final = "0.1.1"

URL_BASE: Final = "/meal_manager_static"
CARD_FILE: Final = "meal-manager-card.js"
PANEL_URL_PATH: Final = "meal-manager"

USER_RECIPES_FILE: Final = "meal_manager_recipes.json"

# Option keys (config entry options)
OPT_GENERAL: Final = "general"
OPT_DEFAULTS: Final = "defaults"
OPT_OVERRIDES: Final = "overrides"
OPT_SLOTS: Final = "slots"

CONF_AI_TASK_ENTITY: Final = "ai_task_entity"
CONF_PREFERENCES: Final = "preferences"
CONF_SHOPPING_LIST: Final = "shopping_list"
CONF_SHOW_PANEL: Final = "show_panel"
CONF_AUTO_NEW_PLAN: Final = "auto_new_plan"
CONF_DEFAULT_DAYS: Final = "default_days"
CONF_AVOID_RECENT: Final = "avoid_recent"

DEFAULT_GENERAL: Final = {
    CONF_AI_TASK_ENTITY: None,
    CONF_PREFERENCES: "",
    CONF_SHOPPING_LIST: None,
    CONF_SHOW_PANEL: True,
    CONF_AUTO_NEW_PLAN: True,
    CONF_DEFAULT_DAYS: 7,
    CONF_AVOID_RECENT: 10,
}

EVENT_PREFIX: Final = f"{DOMAIN}_"
SIGNAL_UPDATE: Final = f"{DOMAIN}_update"
