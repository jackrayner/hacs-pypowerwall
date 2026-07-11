from custom_components.pypowerwall.coordinator import PowerwallData
from custom_components.pypowerwall.sensor import (
    _battery_export_power,
    _battery_import_power,
    _grid_export_power,
    _grid_import_power,
    _trapezoidal_energy_delta_kwh,
)


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


class TestGridImportExportPower:
    """Grid's sign convention is the OPPOSITE of battery's: negative grid_power
    means exporting to the grid, positive means importing -- see sensor.py's
    _grid_import_power docstring for the derivation from pypowerwall's own
    README. These cases mirror pypowerwall's example /api/meters/aggregates
    payload (site.instant_power=-23 while net-exporting), and would fail if the
    sign handling were accidentally copy-pasted from battery's convention.
    """

    def test_negative_grid_power_is_export_only(self):
        data = PowerwallData(grid_power=-23)
        assert _grid_import_power(data) == 0
        assert _grid_export_power(data) == 23

    def test_positive_grid_power_is_import_only(self):
        data = PowerwallData(grid_power=750)
        assert _grid_import_power(data) == 750
        assert _grid_export_power(data) == 0

    def test_idle_grid_is_zero_both_ways(self):
        data = PowerwallData(grid_power=0)
        assert _grid_import_power(data) == 0
        assert _grid_export_power(data) == 0

    def test_missing_grid_power_is_none_both_ways(self):
        data = PowerwallData(grid_power=None)
        assert _grid_import_power(data) is None
        assert _grid_export_power(data) is None


class TestTrapezoidalEnergyDeltaKwh:
    def test_constant_power_for_one_hour(self):
        # 1000W held constant for 3600s (1h) = 1 kWh.
        assert _trapezoidal_energy_delta_kwh(1000, 1000, 3600) == 1.0

    def test_ramping_power_averages_the_two_samples(self):
        # (0W + 2000W) / 2 = 1000W average, held for 1800s (0.5h) = 0.5 kWh.
        assert _trapezoidal_energy_delta_kwh(0, 2000, 1800) == 0.5

    def test_zero_elapsed_time_is_zero_delta(self):
        assert _trapezoidal_energy_delta_kwh(500, 1500, 0) == 0.0

    def test_short_interval_matches_hand_computed_value(self):
        # (100W + 300W) / 2 = 200W average, held for 10s -> 200 * (10/3600) / 1000 kWh.
        result = _trapezoidal_energy_delta_kwh(100, 300, 10)
        assert result == 200 * (10 / 3600) / 1000
