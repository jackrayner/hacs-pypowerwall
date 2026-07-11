"""Select platform for pypowerwall."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PypowerwallConfigEntry
from .coordinator import PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity

# The exact set pypowerwall's own write path validates against (see the mode check
# in pypowerwall/__main__.py) -- other spellings seen in Tesla's own UI/docs
# (e.g. "backup_only") are display labels, not what the write API accepts.
BATTERY_MODES = ["self_consumption", "backup", "autonomous"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PypowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pypowerwall select entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([PowerwallModeSelect(coordinator)])


class PowerwallModeSelect(PowerwallEntity, SelectEntity):
    """Controls the Powerwall's battery operation mode."""

    _attr_translation_key = "battery_mode"
    _attr_options = BATTERY_MODES

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_battery_mode"

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.battery_mode

    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(self.coordinator.pw.set_mode, option)
        await self.coordinator.async_request_refresh()
