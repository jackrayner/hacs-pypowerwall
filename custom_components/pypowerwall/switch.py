"""Switch platform for pypowerwall."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PypowerwallConfigEntry
from .const import CONF_CONN_TYPE, GRID_CONTROL_CONN_TYPES
from .coordinator import PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PypowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pypowerwall switch entities from a config entry."""
    if entry.data[CONF_CONN_TYPE] not in GRID_CONTROL_CONN_TYPES:
        return
    coordinator = entry.runtime_data
    async_add_entities([PowerwallGridChargingSwitch(coordinator)])


class PowerwallGridChargingSwitch(PowerwallEntity, SwitchEntity):
    """Controls whether the Powerwall is allowed to charge its battery from the grid.

    Only created for Cloud/FleetAPI mode entries -- pypowerwall's own docstring for
    set_grid_charging()/get_grid_charging() states this requires Cloud or FleetAPI
    mode and isn't available in local TEDAPI or hybrid mode.
    """

    _attr_translation_key = "grid_charging"

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._din}_grid_charging"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.grid_charging

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.coordinator.pw.set_grid_charging, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.coordinator.pw.set_grid_charging, False)
        await self.coordinator.async_request_refresh()
