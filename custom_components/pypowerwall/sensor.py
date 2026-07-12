"""Sensor platform for pypowerwall."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import PypowerwallConfigEntry
from .coordinator import PowerwallData, PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity


@dataclass(frozen=True, kw_only=True)
class PowerwallSensorDescription(SensorEntityDescription):
    """Describes a pypowerwall sensor backed by a PowerwallData field."""

    value_fn: Callable[[PowerwallData], object]


def _battery_import_power(data: PowerwallData) -> float | None:
    """Power flowing into the battery (charging) as a positive value, else 0."""
    if data.battery_power is None:
        return None
    return max(-data.battery_power, 0)


def _battery_export_power(data: PowerwallData) -> float | None:
    """Power flowing out of the battery (discharging) as a positive value, else 0."""
    if data.battery_power is None:
        return None
    return max(data.battery_power, 0)


def _grid_import_power(data: PowerwallData) -> float | None:
    """Power drawn from the grid as a positive value, else 0.

    Opposite polarity from battery: pypowerwall's own /api/meters/aggregates
    glossary defines the site meter's energy_imported as "kWh pulled from
    grid" and energy_exported as "kWh pushed to grid" (README.md's Example API
    Calls section, further down from the sample payload). In that same sample
    payload, site.instant_power is -23 while the battery (instant_power=1200,
    positive per _battery_export_power's convention) is discharging and, with
    solar's 10W added in, comfortably covers load's 1182.5W with a small
    surplus -- i.e. the home is a net exporter at that instant. So negative
    site/grid instant_power means exporting to the grid, positive means
    importing from it: the reverse of battery_power's charge/discharge sign.
    Don't copy battery's polarity here.
    """
    if data.grid_power is None:
        return None
    return max(data.grid_power, 0)


def _grid_export_power(data: PowerwallData) -> float | None:
    """Power pushed to the grid as a positive value, else 0. See _grid_import_power."""
    if data.grid_power is None:
        return None
    return max(-data.grid_power, 0)


def _trapezoidal_energy_delta_kwh(power1: float, power2: float, elapsed_seconds: float) -> float:
    """Trapezoidal-rule energy (kWh) delta between two power (W) samples.

    Averages the two power readings and multiplies by elapsed time, i.e. the
    area of the trapezoid between them -- a closer approximation of the true
    integral than assuming power was constant at either endpoint for the
    whole interval. W * h / 1000 = kWh.
    """
    avg_power_w = (power1 + power2) / 2
    elapsed_hours = elapsed_seconds / 3600
    return avg_power_w * elapsed_hours / 1000


SENSOR_DESCRIPTIONS: tuple[PowerwallSensorDescription, ...] = (
    PowerwallSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_level,
    ),
    PowerwallSensorDescription(
        key="battery_level_app",
        translation_key="battery_level_app",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery_level_app,
    ),
    PowerwallSensorDescription(
        key="backup_time_remaining",
        translation_key="backup_time_remaining",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.backup_time_remaining,
    ),
    PowerwallSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.grid_power,
    ),
    PowerwallSensorDescription(
        key="grid_import_power",
        translation_key="grid_import_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_grid_import_power,
    ),
    PowerwallSensorDescription(
        key="grid_export_power",
        translation_key="grid_export_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_grid_export_power,
    ),
    PowerwallSensorDescription(
        key="solar_power",
        translation_key="solar_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar_power,
    ),
    PowerwallSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_power,
    ),
    PowerwallSensorDescription(
        key="battery_import_power",
        translation_key="battery_import_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery_import_power,
    ),
    PowerwallSensorDescription(
        key="battery_export_power",
        translation_key="battery_export_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery_export_power,
    ),
    PowerwallSensorDescription(
        key="battery_energy_imported",
        translation_key="battery_energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery_energy_imported,
    ),
    PowerwallSensorDescription(
        key="battery_energy_exported",
        translation_key="battery_energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery_energy_exported,
    ),
    PowerwallSensorDescription(
        key="home_power",
        translation_key="home_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.home_power,
    ),
    PowerwallSensorDescription(
        key="grid_status",
        translation_key="grid_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.grid_status,
    ),
    PowerwallSensorDescription(
        key="alert_count",
        translation_key="alert_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: len(data.alerts),
    ),
    PowerwallSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.version,
    ),
    PowerwallSensorDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.uptime,
    ),
)

# Client-side Riemann-sum (trapezoidal) energy estimates, one per power source_fn
# above -- see PowerwallEnergyIntegrationSensor for why these ship disabled by
# default. (key, translation_key, source_fn) rather than a dataclass since the
# sensor class needs the raw source_fn as a constructor arg, not something read
# off a shared PowerwallSensorDescription-style entity_description.
ENERGY_INTEGRATION_SENSORS: tuple[tuple[str, str, Callable[[PowerwallData], float | None]], ...] = (
    ("battery_import_energy", "battery_import_energy", _battery_import_power),
    ("battery_export_energy", "battery_export_energy", _battery_export_power),
    ("grid_import_energy", "grid_import_energy", _grid_import_power),
    ("grid_export_energy", "grid_export_energy", _grid_export_power),
    ("home_energy", "home_energy", lambda data: data.home_power),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PypowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pypowerwall sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PowerwallSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )

    async_add_entities(
        PowerwallEnergyIntegrationSensor(coordinator, source_fn, key, translation_key)
        for key, translation_key, source_fn in ENERGY_INTEGRATION_SENSORS
    )

    known_temp_devices: set[str] = set()

    @callback
    def _add_new_temp_sensors() -> None:
        new_devices = set(coordinator.data.temps) - known_temp_devices
        if not new_devices:
            return
        known_temp_devices.update(new_devices)
        async_add_entities(PowerwallTempSensor(coordinator, device) for device in new_devices)

    _add_new_temp_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_temp_sensors))


class PowerwallSensor(PowerwallEntity, SensorEntity):
    """A pypowerwall sensor driven by a PowerwallSensorDescription."""

    entity_description: PowerwallSensorDescription

    def __init__(
        self, coordinator: PowerwallDataUpdateCoordinator, description: PowerwallSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)


class PowerwallTempSensor(PowerwallEntity, SensorEntity):
    """A temperature sensor for a single Powerwall battery device."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PowerwallDataUpdateCoordinator, device: str) -> None:
        super().__init__(coordinator)
        self._device = device
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_temp_{device}"
        self._attr_translation_key = "battery_temp"
        self._attr_translation_placeholders = {"device": device}

    @property
    def native_value(self):
        return self.coordinator.data.temps.get(self._device)

    @property
    def available(self) -> bool:
        return super().available and self._device in self.coordinator.data.temps


class PowerwallEnergyIntegrationSensor(PowerwallEntity, RestoreEntity, SensorEntity):
    """Client-side Riemann-sum (trapezoidal) energy estimate for a power source_fn.

    Unlike every other sensor in this platform, this one is stateful: it keeps a
    running total plus the last (power, timestamp) sample so it can integrate
    the trapezoid between consecutive coordinator updates, and it must survive
    Home Assistant restarts without resetting to zero since it's an accumulator
    -- hence RestoreEntity, restoring the running total from the last known
    state in async_added_to_hass rather than the usual pure coordinator-data
    read every other sensor here uses.

    This exists as a fallback for battery_energy_imported/_exported (and a
    same-idea addition for grid/home), which read the gateway's own lifetime
    meter counters and are more accurate -- but on some hardware those fields
    don't populate reliably. A client-side power integration is a strictly
    worse approximation (missed samples between polls, no sub-interval
    resolution) than the real meter, so this ships opt-in only:
    _attr_entity_registry_enabled_default = False on every instance. Don't
    flip that default without discussion -- it's the deliberate point of this
    class.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: PowerwallDataUpdateCoordinator,
        source_fn: Callable[[PowerwallData], float | None],
        key: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._source_fn = source_fn
        din = coordinator.config_entry.unique_id or coordinator.data.din
        self._attr_unique_id = f"{din}_{key}"
        self._attr_translation_key = translation_key
        self._total_kwh = 0.0
        self._last_power: float | None = None
        self._last_updated: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unknown", "unavailable"):
            try:
                self._total_kwh = float(last_state.state)
            except ValueError:
                self._total_kwh = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        current_power = self._source_fn(self.coordinator.data)
        now = dt_util.utcnow()
        if self._last_power is not None and current_power is not None:
            elapsed_seconds = (now - self._last_updated).total_seconds()
            self._total_kwh += _trapezoidal_energy_delta_kwh(
                self._last_power, current_power, elapsed_seconds
            )
        if current_power is not None:
            self._last_power = current_power
            self._last_updated = now
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        return round(self._total_kwh, 3)
