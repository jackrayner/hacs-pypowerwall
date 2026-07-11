"""Sensor platform for pypowerwall."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PypowerwallConfigEntry
from .coordinator import PowerwallData, PowerwallDataUpdateCoordinator
from .entity import PowerwallEntity


@dataclass(frozen=True, kw_only=True)
class PowerwallSensorDescription(SensorEntityDescription):
    """Describes a pypowerwall sensor backed by a PowerwallData field."""

    value_fn: Callable[[PowerwallData], object]


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
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.uptime,
    ),
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
