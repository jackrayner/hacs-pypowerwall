"""The pypowerwall integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    ATTR_DURATION_SECONDS,
    CONF_CONN_TYPE,
    CONN_TYPE_TEDAPI_V1R,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_CLOUD,
    DOMAIN,
    GRID_CONTROL_CONN_TYPES,
    SERVICE_CANCEL_MAX_BACKUP,
    SERVICE_SCHEDULE_MAX_BACKUP,
)
from .coordinator import PowerwallDataUpdateCoordinator, async_connect_powerwall

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
]

type PypowerwallConfigEntry = ConfigEntry[PowerwallDataUpdateCoordinator]

SCHEDULE_MAX_BACKUP_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DURATION_SECONDS, default=7200): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> bool:
    """Set up pypowerwall from a config entry."""
    pw = await async_connect_powerwall(hass, entry.data[CONF_CONN_TYPE], entry.data)

    default_scan_interval = (
        DEFAULT_SCAN_INTERVAL_CLOUD
        if entry.data[CONF_CONN_TYPE] in GRID_CONTROL_CONN_TYPES
        else DEFAULT_SCAN_INTERVAL
    )
    scan_interval = entry.options.get("scan_interval", default_scan_interval)
    coordinator = PowerwallDataUpdateCoordinator(hass, entry, pw, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entry.data[CONF_CONN_TYPE] == CONN_TYPE_TEDAPI_V1R:
        _async_register_v1r_services(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> None:
    """Reload the entry when its options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_v1r_services(hass: HomeAssistant, entry: PypowerwallConfigEntry) -> None:
    """Register the max-backup (storm watch) actions for a v1r LAN mode entry.

    schedule_max_backup()/cancel_max_backup() are momentary actions rather than
    persistent state, so they're exposed as Home Assistant services rather than
    entities. They require v1r LAN mode -- pypowerwall itself checks
    tedapi_mode == "v1r" and no-ops (logs an error, returns None) otherwise, and
    CONN_TYPE_TEDAPI_V1R is the only connection type that puts pypowerwall into
    that mode (see coordinator.build_powerwall_kwargs()).

    Services are domain-scoped rather than per-entry in Home Assistant. If more
    than one v1r entry is configured, the most-recently-set-up entry's
    coordinator is the one these services act on. To keep the services working
    for as long as *any* v1r entry is loaded, we track every currently-loaded
    v1r entry in hass.data (insertion order = setup order): unloading one entry
    re-points the services at another still-loaded v1r entry rather than
    unregistering them outright, and they're only removed once the last v1r
    entry unloads.
    """
    v1r_entries: dict[str, PypowerwallConfigEntry] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "v1r_entries", {}
    )
    v1r_entries[entry.entry_id] = entry

    def _register_for(target_entry: PypowerwallConfigEntry) -> None:
        coordinator = target_entry.runtime_data

        async def _schedule_max_backup(call: ServiceCall) -> None:
            duration_seconds = call.data[ATTR_DURATION_SECONDS]
            await hass.async_add_executor_job(coordinator.pw.schedule_max_backup, duration_seconds)
            await coordinator.async_request_refresh()

        async def _cancel_max_backup(call: ServiceCall) -> None:
            await hass.async_add_executor_job(coordinator.pw.cancel_max_backup)
            await coordinator.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_SCHEDULE_MAX_BACKUP,
            _schedule_max_backup,
            schema=SCHEDULE_MAX_BACKUP_SCHEMA,
        )
        hass.services.async_register(DOMAIN, SERVICE_CANCEL_MAX_BACKUP, _cancel_max_backup)

    _register_for(entry)

    def _remove_services() -> None:
        v1r_entries.pop(entry.entry_id, None)
        if v1r_entries:
            # Another v1r entry is still loaded -- re-point the services at the
            # most-recently-set-up one still around rather than tearing them
            # down out from under it.
            _register_for(next(reversed(v1r_entries.values())))
        else:
            hass.services.async_remove(DOMAIN, SERVICE_SCHEDULE_MAX_BACKUP)
            hass.services.async_remove(DOMAIN, SERVICE_CANCEL_MAX_BACKUP)

    entry.async_on_unload(_remove_services)
