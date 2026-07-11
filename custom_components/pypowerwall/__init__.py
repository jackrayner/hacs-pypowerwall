"""The pypowerwall integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_GW_PWD, DEFAULT_SCAN_INTERVAL
from .coordinator import PowerwallDataUpdateCoordinator, async_connect_powerwall

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type PypowerwallConfigEntry = ConfigEntry[PowerwallDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> bool:
    """Set up pypowerwall from a config entry."""
    pw = await async_connect_powerwall(hass, entry.data[CONF_HOST], entry.data[CONF_GW_PWD])

    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator = PowerwallDataUpdateCoordinator(hass, entry, pw, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> None:
    """Reload the entry when its options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
