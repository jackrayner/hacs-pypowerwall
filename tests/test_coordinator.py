from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD

from custom_components.pypowerwall.const import (
    CONF_AUTHPATH,
    CONF_GW_PWD,
    CONF_RSA_KEY_PATH,
    CONF_SITEID,
    CONF_WIFI_HOST,
    CONN_TYPE_CLOUD,
    CONN_TYPE_FLEETAPI,
    CONN_TYPE_HYBRID,
    CONN_TYPE_LOCAL,
    CONN_TYPE_TEDAPI,
    CONN_TYPE_TEDAPI_V1R,
)
from custom_components.pypowerwall.coordinator import (
    PowerwallData,
    _fetch_data,
    build_powerwall_kwargs,
)


def _make_pw(**overrides):
    pw = MagicMock()
    pw.site_name.return_value = overrides.get("site_name", "Test Site")
    pw.version.return_value = overrides.get("version", "23.44.0")
    pw.din.return_value = overrides.get("din", "1232100-00-E--TG123456789ABC")
    pw.uptime.return_value = overrides.get("uptime", "1 day, 2:03:04")
    pw.grid_status.return_value = overrides.get("grid_status", "UP")
    pw.level.side_effect = lambda scale=False: 60.0 if scale else 55.4
    pw.get_reserve.return_value = overrides.get("battery_reserve", 20.0)
    pw.get_mode.return_value = overrides.get("battery_mode", "self_consumption")
    pw.get_time_remaining.return_value = overrides.get("backup_time_remaining", 12.345)
    pw.grid.return_value = overrides.get("grid_power", 123.456)
    pw.solar.return_value = overrides.get("solar_power", 2345.6)
    battery_power = overrides.get("battery_power", -500.0)
    battery_energy_imported_wh = overrides.get("battery_energy_imported_wh", 5000.0)
    battery_energy_exported_wh = overrides.get("battery_energy_exported_wh", 3000.0)
    pw.battery.side_effect = lambda verbose=False: (
        {
            "instant_power": battery_power,
            "energy_imported": battery_energy_imported_wh,
            "energy_exported": battery_energy_exported_wh,
        }
        if verbose
        else battery_power
    )
    pw.home.return_value = overrides.get("home_power", 1968.0)
    pw.temps.return_value = overrides.get("temps", {"TETHC--abc123": 24.5})
    pw.alerts.return_value = overrides.get("alerts", ["SystemConnectedToGrid"])
    return pw


class TestFetchData:
    def test_maps_all_fields(self):
        pw = _make_pw()
        data = _fetch_data(pw)

        assert isinstance(data, PowerwallData)
        assert data.site_name == "Test Site"
        assert data.din == "1232100-00-E--TG123456789ABC"
        assert data.grid_status == "UP"
        assert data.grid_connected is True
        assert data.battery_level == 55.4
        assert data.battery_level_app == 60.0
        assert data.battery_reserve == 20.0
        assert data.battery_mode == "self_consumption"
        assert data.backup_time_remaining == 12.3
        assert data.grid_power == 123
        assert data.solar_power == 2346
        assert data.battery_power == -500
        assert data.battery_energy_imported == 5.0
        assert data.battery_energy_exported == 3.0
        assert data.home_power == 1968
        assert data.temps == {"TETHC--abc123": 24.5}
        assert data.alerts == ["SystemConnectedToGrid"]

    def test_grid_down_is_not_connected(self):
        data = _fetch_data(_make_pw(grid_status="DOWN"))
        assert data.grid_connected is False

    def test_grid_syncing_is_not_connected(self):
        data = _fetch_data(_make_pw(grid_status="SYNCING"))
        assert data.grid_connected is False

    def test_grid_status_none_leaves_connected_none(self):
        data = _fetch_data(_make_pw(grid_status=None))
        assert data.grid_connected is None
        assert data.grid_status is None

    def test_missing_optional_values_stay_none(self):
        pw = _make_pw()
        pw.get_reserve.return_value = None
        pw.get_time_remaining.return_value = None
        data = _fetch_data(pw)
        assert data.battery_reserve is None
        assert data.backup_time_remaining is None

    def test_alerts_sorted(self):
        data = _fetch_data(_make_pw(alerts=["Zeta", "Alpha"]))
        assert data.alerts == ["Alpha", "Zeta"]

    def test_battery_meter_missing_leaves_power_and_energy_none(self):
        pw = _make_pw()
        pw.battery.side_effect = lambda verbose=False: None
        data = _fetch_data(pw)
        assert data.battery_power is None
        assert data.battery_energy_imported is None
        assert data.battery_energy_exported is None

    def test_missing_temps_and_alerts_default_empty(self):
        pw = _make_pw()
        pw.temps.return_value = None
        pw.alerts.return_value = None
        data = _fetch_data(pw)
        assert data.temps == {}
        assert data.alerts == []

    def test_grid_charging_and_export_not_polled_without_conn_type(self):
        pw = _make_pw()
        data = _fetch_data(pw)
        assert data.grid_charging is None
        assert data.grid_export is None
        pw.get_grid_charging.assert_not_called()
        pw.get_grid_export.assert_not_called()

    def test_grid_charging_and_export_not_polled_for_tedapi(self):
        pw = _make_pw()
        data = _fetch_data(pw, CONN_TYPE_TEDAPI)
        assert data.grid_charging is None
        assert data.grid_export is None
        pw.get_grid_charging.assert_not_called()
        pw.get_grid_export.assert_not_called()

    def test_grid_charging_and_export_polled_for_cloud(self):
        pw = _make_pw()
        pw.get_grid_charging.return_value = True
        pw.get_grid_export.return_value = "pv_only"
        data = _fetch_data(pw, CONN_TYPE_CLOUD)
        assert data.grid_charging is True
        assert data.grid_export == "pv_only"

    def test_grid_charging_and_export_polled_for_fleetapi(self):
        pw = _make_pw()
        pw.get_grid_charging.return_value = False
        pw.get_grid_export.return_value = "never"
        data = _fetch_data(pw, CONN_TYPE_FLEETAPI)
        assert data.grid_charging is False
        assert data.grid_export == "never"


class TestBuildPowerwallKwargs:
    def test_local(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_LOCAL,
            {CONF_HOST: "10.0.0.1", CONF_EMAIL: "owner@example.com", CONF_PASSWORD: "pw"},
        )
        assert kwargs == {"host": "10.0.0.1", "email": "owner@example.com", "password": "pw"}

    def test_tedapi(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_TEDAPI, {CONF_HOST: "192.168.91.1", CONF_GW_PWD: "gw"}
        )
        assert kwargs == {"host": "192.168.91.1", "gw_pwd": "gw"}

    def test_hybrid(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_HYBRID,
            {
                CONF_HOST: "h",
                CONF_EMAIL: "e@example.com",
                CONF_PASSWORD: "p",
                CONF_GW_PWD: "g",
            },
        )
        assert kwargs == {"host": "h", "email": "e@example.com", "password": "p", "gw_pwd": "g"}

    def test_tedapi_v1r_minimal(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_TEDAPI_V1R,
            {CONF_HOST: "h", CONF_GW_PWD: "g", CONF_RSA_KEY_PATH: "/key.pem"},
        )
        assert kwargs == {"host": "h", "gw_pwd": "g", "rsa_key_path": "/key.pem"}

    def test_tedapi_v1r_with_wifi_host(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_TEDAPI_V1R,
            {
                CONF_HOST: "h",
                CONF_GW_PWD: "g",
                CONF_RSA_KEY_PATH: "/key.pem",
                CONF_WIFI_HOST: "10.0.0.5",
            },
        )
        assert kwargs["wifi_host"] == "10.0.0.5"

    def test_cloud_minimal(self):
        kwargs = build_powerwall_kwargs(CONN_TYPE_CLOUD, {CONF_AUTHPATH: "/auth"})
        assert kwargs == {"cloudmode": True, "authpath": "/auth"}

    def test_cloud_with_siteid(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_CLOUD, {CONF_AUTHPATH: "/auth", CONF_SITEID: "123"}
        )
        assert kwargs == {"cloudmode": True, "authpath": "/auth", "siteid": "123"}

    def test_fleetapi_minimal(self):
        kwargs = build_powerwall_kwargs(CONN_TYPE_FLEETAPI, {CONF_AUTHPATH: "/auth"})
        assert kwargs == {"fleetapi": True, "cloudmode": True, "authpath": "/auth"}

    def test_fleetapi_with_siteid(self):
        kwargs = build_powerwall_kwargs(
            CONN_TYPE_FLEETAPI, {CONF_AUTHPATH: "/auth", CONF_SITEID: "456"}
        )
        assert kwargs == {
            "fleetapi": True,
            "cloudmode": True,
            "authpath": "/auth",
            "siteid": "456",
        }

    def test_unknown_conn_type_raises(self):
        with pytest.raises(ValueError):
            build_powerwall_kwargs("bogus", {})
