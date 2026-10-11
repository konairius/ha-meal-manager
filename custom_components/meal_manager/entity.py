"""Base entity: refreshes whenever the planner changes."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import MealManagerConfigEntry
from .const import DOMAIN, SIGNAL_UPDATE, VERSION


class MealManagerEntity(Entity):
    """Common base of all Meal Manager entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: MealManagerConfigEntry, key: str) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Meal Manager",
            entry_type=DeviceEntryType.SERVICE,
            sw_version=VERSION,
        )

    @property
    def data(self):
        return self._entry.runtime_data

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self.async_write_ha_state))
