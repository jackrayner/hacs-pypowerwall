"""Select platform for pypowerwall."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PypowerwallConfigEntry
from .const import CONF_CONN_TYPE, GRID_CONTROL_CONN_TYPES
from .coordinator import PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity

# The exact set pypowerwall's own write path validates against (see the mode check
# in pypowerwall/__main__.py) -- other spellings seen in Tesla's own UI/docs
# (e.g. "backup_only") are display labels, not what the write API accepts.
BATTERY_MODES = ["self_consumption", "backup", "autonomous"]

# The exact set pypowerwall's set_grid_export() validates against.
GRID_EXPORT_MODES = ["battery_ok", "pv_only", "never"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PypowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pypowerwall select entities from a config entry."""
    coordinator = entry.runtime_data
    entities: list[PowerwallEntity] = [PowerwallModeSelect(coordinator)]
    # set_grid_export()/get_grid_export() require Cloud or FleetAPI mode per pypowerwall's
    # own docstring -- not available in local TEDAPI or hybrid mode.
    if entry.data[CONF_CONN_TYPE] in GRID_CONTROL_CONN_TYPES:
        entities.append(PowerwallGridExportSelect(coordinator))
    async_add_entities(entities)


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


class PowerwallGridExportSelect(PowerwallEntity, SelectEntity):
    """Controls the Powerwall's grid export policy.

    Only created for Cloud/FleetAPI mode entries -- see GRID_CONTROL_CONN_TYPES.
    """

    _attr_translation_key = "grid_export"
    _attr_options = GRID_EXPORT_MODES

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_grid_export"

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.grid_export

    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(self.coordinator.pw.set_grid_export, option)
        await self.coordinator.async_request_refresh()
