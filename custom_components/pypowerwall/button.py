"""Button platform for pypowerwall."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up pypowerwall button entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            PowerwallGoOffGridButton(coordinator),
            PowerwallReconnectGridButton(coordinator),
        ]
    )


class PowerwallGoOffGridButton(PowerwallEntity, ButtonEntity):
    """Physically opens the grid contactor, islanding the home from the grid.

    Real-world effect: the home is disconnected from the utility grid. Solar
    keeps producing and the battery serves home load, but there is a ~30s
    solar production dropout during the contactor transition.

    As of pypowerwall 0.16.1, go_off_grid() is a facade method that only
    forwards to a backend implementation if one exists (checked via
    hasattr(self.client, 'go_off_grid')); none of the local/TEDAPI/hybrid/
    cloud/FleetAPI backends implement it yet, so today this gracefully no-ops
    (pypowerwall logs an error and returns None) regardless of connection
    type. This entity is intentionally left ungated across connection types
    for that reason -- unlike the Cloud/FleetAPI-only entities in switch.py/
    select.py, there is currently no connection type for which this button
    is *known* to work, so gating on conn_type would just hide it from
    everyone. It's kept as forward-compatible surface for when a backend
    adds support.

    Disabled by default (_attr_entity_registry_enabled_default = False):
    given the real-world effect above, this must not be enabled without the
    user explicitly opting in via the entity's settings.
    """

    _attr_translation_key = "go_off_grid"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_go_off_grid"

    async def async_press(self) -> None:
        # A deliberate press of this button already IS the explicit
        # confirmation pypowerwall's go_off_grid() requires, so confirm=True
        # is always passed here.
        await self.hass.async_add_executor_job(self.coordinator.pw.go_off_grid, True)
        await self.coordinator.async_request_refresh()


class PowerwallReconnectGridButton(PowerwallEntity, ButtonEntity):
    """Physically closes the grid contactor, reconnecting the home to the grid.

    See PowerwallGoOffGridButton's docstring for why this isn't gated by
    connection type.
    """

    _attr_translation_key = "reconnect_grid"

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_reconnect_grid"

    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.coordinator.pw.reconnect_grid)
        await self.coordinator.async_request_refresh()
