"""Data update coordinator for the pypowerwall integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

import pypowerwall
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerwallData:
    """A snapshot of Powerwall metrics for one poll cycle."""

    site_name: str | None = None
    version: str | None = None
    din: str | None = None
    uptime: str | None = None
    grid_status: str | None = None
    grid_connected: bool | None = None
    battery_level: float | None = None
    battery_level_app: float | None = None
    battery_reserve: float | None = None
    battery_mode: str | None = None
    backup_time_remaining: float | None = None
    grid_power: float | None = None
    solar_power: float | None = None
    battery_power: float | None = None
    home_power: float | None = None
    temps: dict[str, float] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


def _safe_round(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def _fetch_data(pw: pypowerwall.Powerwall) -> PowerwallData:
    grid_status = pw.grid_status()
    return PowerwallData(
        site_name=pw.site_name(),
        version=pw.version(),
        din=pw.din(),
        uptime=pw.uptime(),
        grid_status=grid_status,
        grid_connected=grid_status == "UP" if grid_status is not None else None,
        battery_level=_safe_round(pw.level(), 1),
        battery_level_app=_safe_round(pw.level(scale=True), 1),
        battery_reserve=_safe_round(pw.get_reserve(), 1),
        battery_mode=pw.get_mode(),
        backup_time_remaining=_safe_round(pw.get_time_remaining(), 1),
        grid_power=_safe_round(pw.grid(), 0),
        solar_power=_safe_round(pw.solar(), 0),
        battery_power=_safe_round(pw.battery(), 0),
        home_power=_safe_round(pw.home(), 0),
        temps=pw.temps() or {},
        alerts=sorted(pw.alerts() or []),
    )


class PowerwallDataUpdateCoordinator(DataUpdateCoordinator[PowerwallData]):
    """Coordinator that polls a pypowerwall.Powerwall client on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pw: pypowerwall.Powerwall,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.pw = pw

    async def _async_update_data(self) -> PowerwallData:
        try:
            data = await self.hass.async_add_executor_job(_fetch_data, self.pw)
        except Exception as exc:  # noqa: BLE001 - pypowerwall raises plain Exception on failures
            raise UpdateFailed(f"Error communicating with Powerwall: {exc}") from exc
        if data.din is None:
            raise UpdateFailed("Powerwall did not return a status payload")
        return data


async def async_connect_powerwall(
    hass: HomeAssistant, host: str, gw_pwd: str
) -> pypowerwall.Powerwall:
    """Create and connect a Powerwall client in the executor, raising on failure."""

    def _connect() -> pypowerwall.Powerwall:
        pw = pypowerwall.Powerwall(host, gw_pwd=gw_pwd)
        if not pw.is_connected():
            raise ConfigEntryNotReady(f"Unable to connect to Powerwall at {host}")
        return pw

    return await hass.async_add_executor_job(_connect)
