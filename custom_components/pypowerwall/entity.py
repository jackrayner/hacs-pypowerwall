"""Base entity for pypowerwall."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PowerwallDataUpdateCoordinator


class PowerwallEntity(CoordinatorEntity[PowerwallDataUpdateCoordinator]):
    """Base entity tying sensors to the Powerwall gateway device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, din)},
            manufacturer=MANUFACTURER,
            name=coordinator.data.site_name or "Powerwall",
            model="Powerwall Gateway",
            sw_version=coordinator.data.version,
            serial_number=din,
        )
