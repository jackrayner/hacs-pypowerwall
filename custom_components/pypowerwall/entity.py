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
        # The DIN identifies the physical gateway and can't change for the lifetime
        # of a config entry, so it's fixed at init time -- unlike device_info below,
        # which is derived live so it reflects the latest poll.
        self._din = coordinator.config_entry.unique_id or coordinator.data.din

    @property
    def din(self) -> str:
        """The Powerwall gateway's DIN, fixed for the lifetime of this entity."""
        return self._din

    @property
    def device_info(self) -> DeviceInfo:
        """Device info, derived live from the coordinator's latest data.

        Computed on each access (rather than cached once in __init__) so that a
        firmware update or site rename is reflected on the HA device page without
        requiring a reload of the config entry.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self._din)},
            manufacturer=MANUFACTURER,
            name=self.coordinator.data.site_name or "Powerwall",
            model="Powerwall Gateway",
            sw_version=self.coordinator.data.version,
            serial_number=self._din,
        )
