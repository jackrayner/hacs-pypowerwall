from unittest.mock import MagicMock

import pytest

DIN = "1232100-00-E--TG123456789ABC"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def make_fake_pw(**overrides) -> MagicMock:
    """A fully-stubbed pypowerwall.Powerwall double.

    Creating a config entry via the config flow triggers a real integration
    setup (DataUpdateCoordinator + platforms), so every method the
    coordinator calls must return a JSON-serializable value rather than an
    auto-generated MagicMock, or Home Assistant's storage layer blows up
    trying to persist the device/entity registries.
    """
    pw = MagicMock()
    pw.is_connected.return_value = overrides.get("connected", True)
    pw.din.return_value = overrides.get("din", DIN)
    pw.site_name.return_value = overrides.get("site_name", "Home")
    pw.version.return_value = overrides.get("version", "24.4.0")
    pw.uptime.return_value = overrides.get("uptime", "1:00:00")
    pw.grid_status.return_value = overrides.get("grid_status", "UP")
    level = overrides.get("battery_level", 42.0)
    level_app = overrides.get("battery_level_app", 45.0)
    pw.level.side_effect = lambda scale=False: level_app if scale else level
    pw.get_reserve.return_value = overrides.get("battery_reserve", 20.0)
    pw.get_mode.return_value = overrides.get("battery_mode", "self_consumption")
    pw.get_time_remaining.return_value = overrides.get("backup_time_remaining", 10.0)
    pw.grid.return_value = overrides.get("grid_power", 100.0)
    pw.solar.return_value = overrides.get("solar_power", 500.0)
    pw.battery.return_value = overrides.get("battery_power", -50.0)
    pw.home.return_value = overrides.get("home_power", 550.0)
    pw.temps.return_value = overrides.get("temps", {"TETHC--1": 25.0})
    pw.alerts.return_value = overrides.get("alerts", [])
    pw.get_grid_charging.return_value = overrides.get("grid_charging", True)
    pw.get_grid_export.return_value = overrides.get("grid_export", "battery_ok")
    pw.schedule_max_backup.return_value = {"result": "ok"}
    pw.cancel_max_backup.return_value = {"result": "ok"}
    pw.go_off_grid.return_value = {"result": "ok"}
    pw.reconnect_grid.return_value = {"result": "ok"}
    return pw
