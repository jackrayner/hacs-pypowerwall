from unittest.mock import patch

from conftest import DIN, make_fake_pw
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pypowerwall.const import (
    CONF_CONN_TYPE,
    CONF_GW_PWD,
    CONN_TYPE_TEDAPI,
    DOMAIN,
)

CONNECT_TARGET = "custom_components.pypowerwall.coordinator.pypowerwall.Powerwall"
ENTRY_DATA = {CONF_CONN_TYPE: CONN_TYPE_TEDAPI, "host": "192.168.91.1", CONF_GW_PWD: "secret"}


def _entity_state(hass: HomeAssistant, platform: str, unique_id: str):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{DIN}_{unique_id}")
    assert entity_id is not None, f"no {platform} entity registered for unique_id {unique_id}"
    return hass.states.get(entity_id)


async def test_setup_creates_entities_and_unload_removes_them(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    battery = _entity_state(hass, "sensor", "battery_level")
    assert float(battery.state) == 42.0

    grid_power = _entity_state(hass, "sensor", "grid_power")
    assert float(grid_power.state) == 100.0

    # conftest's default battery_power is -50.0 (charging), so import > 0, export == 0.
    battery_import_power = _entity_state(hass, "sensor", "battery_import_power")
    assert float(battery_import_power.state) == 50.0

    battery_export_power = _entity_state(hass, "sensor", "battery_export_power")
    assert float(battery_export_power.state) == 0.0

    battery_energy_imported = _entity_state(hass, "sensor", "battery_energy_imported")
    assert float(battery_energy_imported.state) == 5.0
    assert battery_energy_imported.attributes["state_class"] == "total_increasing"
    assert battery_energy_imported.attributes["device_class"] == "energy"

    battery_energy_exported = _entity_state(hass, "sensor", "battery_energy_exported")
    assert float(battery_energy_exported.state) == 3.0

    grid_connected = _entity_state(hass, "binary_sensor", "grid_connected")
    assert grid_connected.state == "on"

    temp = _entity_state(hass, "sensor", "temp_TETHC--1")
    assert float(temp.state) == 25.0

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, DIN)})
    assert device is not None
    assert device.serial_number == DIN

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_grid_down_marks_binary_sensor_off(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    pw = make_fake_pw()
    pw.grid_status.return_value = "DOWN"

    with patch(CONNECT_TARGET, return_value=pw):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    grid_connected = _entity_state(hass, "binary_sensor", "grid_connected")
    assert grid_connected.state == "off"


async def test_setup_fails_when_not_connected(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    pw = make_fake_pw()
    pw.is_connected.return_value = False

    with patch(CONNECT_TARGET, return_value=pw):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
