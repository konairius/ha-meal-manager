"""Config and options flow.

All planning settings live in the options. Every setting can be a fixed value, an entity
(optionally an attribute of it) or both; the fixed value is the fallback for the entity.
"""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_AUTO_NEW_PLAN,
    CONF_AVOID_RECENT,
    CONF_DEFAULT_DAYS,
    CONF_PANTRY,
    CONF_PREFERENCES,
    CONF_SEASON,
    CONF_SHOPPING_LANGUAGE,
    CONF_SHOPPING_LIST,
    CONF_SHOW_PANEL,
    DEFAULT_GENERAL,
    DOMAIN,
    OPT_DEFAULTS,
    OPT_GENERAL,
    OPT_OVERRIDES,
    OPT_SLOTS,
    SEASON_MODES,
    SHOPPING_LANGUAGES,
)
from .core.settings import (
    DAY_SCOPED,
    DEFAULT_SLOTS,
    WEEKDAYS,
    Override,
    PlannerSettings,
    Setting,
    ValueSource,
    is_valid,
)

CONF_VALUE = "value"
CONF_ENTITY = "entity_id"
CONF_ATTRIBUTE = "attribute"
CONF_WEEKDAY = "weekday"
CONF_SLOT = "slot"
CONF_SETTING = "setting"
CONF_REMOVE = "remove"
CONF_TIME = "time"
CONF_SHARE = "share"
CONF_PRIORITY = "priority"
CONF_ENABLED = "enabled"
CONF_MEALS_PER_DAY = "meals_per_day"
ANY = "any"

# Settings on the "Default settings" page; meals per day lives on "Meals of the day".
DEFAULT_FIELDS = tuple(s for s in Setting if s is not Setting.MEALS_PER_DAY)


def value_selector(setting: Setting) -> selector.Selector:
    if setting is Setting.EFFORT:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["1", "2", "3"],
                translation_key="effort",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    if setting is Setting.HEALTH:
        return selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=5, step=1, mode=selector.NumberSelectorMode.SLIDER)
        )
    if setting is Setting.CALORIES:
        return selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=8000, step=50, unit_of_measurement="kcal", mode=selector.NumberSelectorMode.BOX
            )
        )
    maximum = len(DEFAULT_SLOTS) if setting is Setting.MEALS_PER_DAY else 30
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=1, max=maximum, step=1, mode=selector.NumberSelectorMode.BOX)
    )


def source_fields(setting: Setting, current: ValueSource) -> dict[Any, Any]:
    """Value + entity + attribute fields for one setting, prefilled with the current source."""

    def opt(key: str, value: Any) -> vol.Optional:
        if value in (None, ""):
            return vol.Optional(key)
        if setting is Setting.EFFORT and key == CONF_VALUE:
            value = str(value)
        return vol.Optional(key, description={"suggested_value": value})

    return {
        opt(CONF_VALUE, current.value): value_selector(setting),
        opt(CONF_ENTITY, current.entity_id): selector.EntitySelector(),
        opt(CONF_ATTRIBUTE, current.attribute): selector.TextSelector(),
    }


def source_from_input(data: dict[str, Any]) -> ValueSource:
    value = data.get(CONF_VALUE)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return ValueSource(
        value=value if value not in ("", None) else None,
        entity_id=data.get(CONF_ENTITY) or None,
        attribute=(data.get(CONF_ATTRIBUTE) or "").strip() or None,
    )


def default_options() -> dict[str, Any]:
    return {
        OPT_GENERAL: dict(DEFAULT_GENERAL),
        OPT_DEFAULTS: {},
        OPT_OVERRIDES: [],
        OPT_SLOTS: [s.to_dict() for s in DEFAULT_SLOTS],
    }


class MealManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the (single) Meal Manager entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Meal Manager", data={}, options=default_options())
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MealManagerOptionsFlow()


class MealManagerOptionsFlow(OptionsFlow):
    """Edit general options, defaults, meal slots and overrides."""

    def __init__(self) -> None:
        self._override: dict[str, Any] = {}

    @property
    def _options(self) -> dict[str, Any]:
        return {**default_options(), **copy.deepcopy(dict(self.config_entry.options))}

    @property
    def _settings(self) -> PlannerSettings:
        return PlannerSettings.from_dict(self._options)

    def _save(self, key: str, value: Any) -> ConfigFlowResult:
        return self.async_create_entry(data={**self._options, key: value})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        menu = ["general", "defaults", "slots", "add_override"]
        if self._settings.overrides:
            menu.append("remove_override")
        return self.async_show_menu(step_id="init", menu_options=menu)

    # ------------------------------------------------------------------ general

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            general = {**DEFAULT_GENERAL, **user_input}
            general[CONF_DEFAULT_DAYS] = int(general[CONF_DEFAULT_DAYS])
            general[CONF_AVOID_RECENT] = int(general[CONF_AVOID_RECENT])
            for key in (CONF_AI_TASK_ENTITY, CONF_SHOPPING_LIST):
                general[key] = user_input.get(key) or None
            general[CONF_PANTRY] = user_input.get(CONF_PANTRY, "")  # empty: everything is bought
            return self._save(OPT_GENERAL, general)

        current = {**DEFAULT_GENERAL, **self._options[OPT_GENERAL]}

        def suggested(key: str) -> dict[str, Any] | None:
            value = current.get(key)
            return {"suggested_value": value} if value not in (None, "") else None

        schema = vol.Schema(
            {
                vol.Optional(CONF_AI_TASK_ENTITY, description=suggested(CONF_AI_TASK_ENTITY)): (
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="ai_task"))
                ),
                vol.Optional(CONF_PREFERENCES, description=suggested(CONF_PREFERENCES)): (
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True))
                ),
                vol.Optional(CONF_SHOPPING_LIST, description=suggested(CONF_SHOPPING_LIST)): (
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="todo"))
                ),
                vol.Required(
                    CONF_SHOPPING_LANGUAGE, default=current[CONF_SHOPPING_LANGUAGE]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(SHOPPING_LANGUAGES),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_SHOPPING_LANGUAGE,
                    )
                ),
                vol.Optional(CONF_PANTRY, description=suggested(CONF_PANTRY)): (
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True))
                ),
                vol.Required(CONF_DEFAULT_DAYS, default=current[CONF_DEFAULT_DAYS]): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=31, mode=selector.NumberSelectorMode.BOX)
                    )
                ),
                vol.Required(CONF_AVOID_RECENT, default=current[CONF_AVOID_RECENT]): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=50, mode=selector.NumberSelectorMode.BOX)
                    )
                ),
                vol.Required(CONF_SEASON, default=current[CONF_SEASON]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(SEASON_MODES),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_SEASON,
                    )
                ),
                vol.Required(CONF_AUTO_NEW_PLAN, default=current[CONF_AUTO_NEW_PLAN]): bool,
                vol.Required(CONF_SHOW_PANEL, default=current[CONF_SHOW_PANEL]): bool,
            }
        )
        return self.async_show_form(step_id="general", data_schema=schema)

    # ----------------------------------------------------------------- defaults

    async def async_step_defaults(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        settings = self._settings
        if user_input is not None:
            # Meals per day is edited on the "Meals of the day" page.
            defaults: dict[str, Any] = {
                str(k): v.to_dict() for k, v in settings.defaults.items() if k not in DEFAULT_FIELDS
            }
            for setting in DEFAULT_FIELDS:
                source = source_from_input(user_input.get(str(setting), {}))
                if source.value is not None and not is_valid(setting, source.value):
                    errors[str(setting)] = "invalid_value"
                if not source.is_empty:
                    defaults[str(setting)] = source.to_dict()
            if not errors:
                return self._save(OPT_DEFAULTS, defaults)

        schema = vol.Schema(
            {
                vol.Required(str(setting)): section(
                    vol.Schema(source_fields(setting, settings.defaults.get(setting, ValueSource()))),
                    {"collapsed": False},
                )
                for setting in DEFAULT_FIELDS
            }
        )
        return self.async_show_form(step_id="defaults", data_schema=schema, errors=errors)

    # -------------------------------------------------------------------- slots

    async def async_step_slots(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which meals are planned, how many per day, their time, calorie share and priority."""
        settings = self._settings
        slots = {s.name: s for s in settings.slots}
        errors: dict[str, str] = {}
        if user_input is not None:
            updated = []
            for name, slot in slots.items():
                values = user_input.get(name, {})
                updated.append(
                    {
                        **slot.to_dict(),
                        "enabled": bool(values.get(CONF_ENABLED, slot.enabled)),
                        "time": str(values.get(CONF_TIME, slot.time))[:5],
                        "share": float(values.get(CONF_SHARE, slot.share)),
                        "priority": int(values.get(CONF_PRIORITY, slot.priority)),
                    }
                )
            per_day = source_from_input(user_input.get(CONF_MEALS_PER_DAY, {}))
            if not any(s["enabled"] for s in updated):
                errors["base"] = "no_meal_enabled"
            elif per_day.value is not None and not is_valid(Setting.MEALS_PER_DAY, per_day.value):
                errors[CONF_MEALS_PER_DAY] = "invalid_value"
            else:
                defaults = {str(k): v.to_dict() for k, v in settings.defaults.items()}
                if per_day.is_empty:
                    defaults.pop(str(Setting.MEALS_PER_DAY), None)
                else:
                    defaults[str(Setting.MEALS_PER_DAY)] = per_day.to_dict()
                return self.async_create_entry(
                    data={**self._options, OPT_SLOTS: updated, OPT_DEFAULTS: defaults}
                )

        per_day_source = settings.defaults.get(Setting.MEALS_PER_DAY, ValueSource())
        fields: dict[Any, Any] = {
            vol.Required(CONF_MEALS_PER_DAY): section(
                vol.Schema(source_fields(Setting.MEALS_PER_DAY, per_day_source)),
                {"collapsed": False},
            )
        }
        for name, slot in slots.items():
            fields[vol.Required(name)] = section(
                vol.Schema(
                    {
                        vol.Required(CONF_ENABLED, default=slot.enabled): bool,
                        vol.Required(CONF_TIME, default=f"{slot.time}:00"): selector.TimeSelector(),
                        vol.Required(CONF_SHARE, default=slot.share): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=100,
                                unit_of_measurement="%",
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Required(CONF_PRIORITY, default=slot.priority): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1, max=len(slots), mode=selector.NumberSelectorMode.BOX
                            )
                        ),
                    }
                ),
                {"collapsed": not slot.enabled},
            )
        return self.async_show_form(step_id="slots", data_schema=vol.Schema(fields), errors=errors)

    # ---------------------------------------------------------------- overrides

    async def async_step_add_override(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            setting = Setting(user_input[CONF_SETTING])
            weekday, slot = user_input[CONF_WEEKDAY], user_input[CONF_SLOT]
            if weekday == ANY and slot == ANY:
                errors["base"] = "scope_required"
            elif setting in DAY_SCOPED and slot != ANY:
                errors[CONF_SLOT] = "day_scoped"
            else:
                self._override = {
                    CONF_SETTING: setting,
                    CONF_WEEKDAY: None if weekday == ANY else WEEKDAYS.index(weekday),
                    CONF_SLOT: None if slot == ANY else slot,
                }
                return await self.async_step_override_value()

        def select(options: list[str], key: str) -> selector.SelectSelector:
            return selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options, translation_key=key, mode=selector.SelectSelectorMode.DROPDOWN
                )
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SETTING, default=str(Setting.PORTIONS)): select(
                    [str(s) for s in Setting], CONF_SETTING
                ),
                vol.Required(CONF_WEEKDAY, default=ANY): select([ANY, *WEEKDAYS], CONF_WEEKDAY),
                vol.Required(CONF_SLOT, default=ANY): select(
                    [ANY, *(s.name for s in self._settings.slots)], CONF_SLOT
                ),
            }
        )
        return self.async_show_form(step_id="add_override", data_schema=schema, errors=errors)

    async def async_step_override_value(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        setting: Setting = self._override[CONF_SETTING]
        errors: dict[str, str] = {}
        if user_input is not None:
            source = source_from_input(user_input)
            if source.is_empty:
                errors["base"] = "value_required"
            elif source.value is not None and not is_valid(setting, source.value):
                errors[CONF_VALUE] = "invalid_value"
            else:
                override = Override(
                    setting=setting,
                    source=source,
                    weekday=self._override[CONF_WEEKDAY],
                    slot=self._override[CONF_SLOT],
                )
                others = [o for o in self._settings.overrides if o.key != override.key]
                return self._save(OPT_OVERRIDES, [o.to_dict() for o in [*others, override]])

        existing = next(
            (
                o.source
                for o in self._settings.overrides
                if o.setting is setting
                and o.weekday == self._override[CONF_WEEKDAY]
                and o.slot == self._override[CONF_SLOT]
            ),
            ValueSource(),
        )
        return self.async_show_form(
            step_id="override_value",
            data_schema=vol.Schema(source_fields(setting, existing)),
            errors=errors,
            description_placeholders={
                "setting": str(setting),
                "scope": scope_label(self._override[CONF_WEEKDAY], self._override[CONF_SLOT]),
            },
        )

    async def async_step_remove_override(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        overrides = self._settings.overrides
        if user_input is not None:
            remove = set(user_input.get(CONF_REMOVE, []))
            return self._save(OPT_OVERRIDES, [o.to_dict() for o in overrides if o.key not in remove])

        options = [selector.SelectOptionDict(value=o.key, label=describe_override(o)) for o in overrides]
        schema = vol.Schema(
            {
                vol.Optional(CONF_REMOVE, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, multiple=True, mode=selector.SelectSelectorMode.LIST
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_override", data_schema=schema)


def scope_label(weekday: int | None, slot: str | None) -> str:
    day = WEEKDAYS[weekday].capitalize() if weekday is not None else ""
    return " ".join(p for p in (day, slot or "") if p)


def describe_override(override: Override) -> str:
    scope = scope_label(override.weekday, override.slot)
    source = override.source
    parts = []
    if source.entity_id:
        parts.append(source.entity_id + (f"[{source.attribute}]" if source.attribute else ""))
    if source.value is not None:
        parts.append(f"{'fallback ' if source.entity_id else ''}{source.value}")
    return f"{scope}: {override.setting} = {', '.join(parts)}"
