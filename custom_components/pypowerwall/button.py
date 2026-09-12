"""Button platform for pypowerwall."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PypowerwallConfigEntry
from .const import CONF_CONN_TYPE, GRID_ISLANDING_CONN_TYPES
from .coordinator import PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PypowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pypowerwall button entities from a config entry."""
    if entry.data[CONF_CONN_TYPE] not in GRID_ISLANDING_CONN_TYPES:
        return
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

    As of pypowerwall 0.17.3, go_off_grid() is a facade method that only
    forwards to a backend implementation if one exists, and the only backend
    that actually implements it is TEDAPI's signed v1r transport
    (send_island_mode()) -- i.e. it works only when the client was constructed
    with v1r=True. Local/TEDAPI (non-v1r)/hybrid/cloud/FleetAPI backends still
    no-op (pypowerwall logs an error and returns None). This entity is
    therefore only created for CONN_TYPE_TEDAPI_V1R entries (see
    GRID_ISLANDING_CONN_TYPES in const.py) -- the same connection-type gating
    pattern the Cloud/FleetAPI-only entities in switch.py/select.py use for
    grid charging/export.

    Disabled by default (_attr_entity_registry_enabled_default = False):
    given the real-world effect above, this must not be enabled without the
    user explicitly opting in via the entity's settings.
    """

    _attr_translation_key = "go_off_grid"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._din}_go_off_grid"

    async def async_press(self) -> None:
        # A deliberate press of this button already IS the explicit
        # confirmation pypowerwall's go_off_grid() requires, so confirm=True
        # is always passed here.
        await self.hass.async_add_executor_job(self.coordinator.pw.go_off_grid, True)
        await self.coordinator.async_request_refresh()


class PowerwallReconnectGridButton(PowerwallEntity, ButtonEntity):
    """Physically closes the grid contactor, reconnecting the home to the grid.

    Like PowerwallGoOffGridButton, reconnect_grid() is only implemented by
    pypowerwall's TEDAPI v1r backend (as of 0.17.3), so this entity is only
    created for CONN_TYPE_TEDAPI_V1R entries -- see GRID_ISLANDING_CONN_TYPES
    in const.py and PowerwallGoOffGridButton's docstring for details.

    Left enabled by default, unlike the go-off-grid button: this is the
    recovery action (closing the contactor, restoring grid connection) rather
    than the risky one, so there's no equivalent case for opt-in-only.
    """

    _attr_translation_key = "reconnect_grid"

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._din}_reconnect_grid"

    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.coordinator.pw.reconnect_grid)
        await self.coordinator.async_request_refresh()
