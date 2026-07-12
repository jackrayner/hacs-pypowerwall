from custom_components.pypowerwall.coordinator import PowerwallData
from custom_components.pypowerwall.sensor import _battery_export_power, _battery_import_power


class TestBatteryImportExportPower:
    def test_charging_is_import_only(self):
        data = PowerwallData(battery_power=-500)
        assert _battery_import_power(data) == 500
        assert _battery_export_power(data) == 0

    def test_discharging_is_export_only(self):
        data = PowerwallData(battery_power=750)
        assert _battery_import_power(data) == 0
        assert _battery_export_power(data) == 750

    def test_idle_battery_is_zero_both_ways(self):
        data = PowerwallData(battery_power=0)
        assert _battery_import_power(data) == 0
        assert _battery_export_power(data) == 0

    def test_missing_battery_power_is_none_both_ways(self):
        data = PowerwallData(battery_power=None)
        assert _battery_import_power(data) is None
        assert _battery_export_power(data) is None
