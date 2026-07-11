from unittest.mock import MagicMock

from custom_components.pypowerwall.coordinator import PowerwallData, _fetch_data


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
    pw.battery.return_value = overrides.get("battery_power", -500.0)
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

    def test_missing_temps_and_alerts_default_empty(self):
        pw = _make_pw()
        pw.temps.return_value = None
        pw.alerts.return_value = None
        data = _fetch_data(pw)
        assert data.temps == {}
        assert data.alerts == []
