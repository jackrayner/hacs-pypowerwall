"""Binary sensor platform for pypowerwall."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PypowerwallConfigEntry
from .coordinator import PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PypowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pypowerwall binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([PowerwallGridConnectedBinarySensor(coordinator)])


class PowerwallGridConnectedBinarySensor(PowerwallEntity, BinarySensorEntity):
    """Whether the Powerwall gateway is currently connected to the grid."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "grid_connected"

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_grid_connected"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.grid_connected
