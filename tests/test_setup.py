from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pypowerwall.const import CONF_GW_PWD, DOMAIN

from conftest import DIN, make_fake_pw

CONNECT_TARGET = "custom_components.pypowerwall.coordinator.pypowerwall.Powerwall"


def _entity_state(hass: HomeAssistant, platform: str, unique_id: str):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{DIN}_{unique_id}")
    assert entity_id is not None, f"no {platform} entity registered for unique_id {unique_id}"
    return hass.states.get(entity_id)


async def test_setup_creates_entities_and_unload_removes_them(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data={"host": "192.168.91.1", CONF_GW_PWD: "secret"},
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

    grid_connected = _entity_state(hass, "binary_sensor", "grid_connected")
    assert grid_connected.state == "on"

    temp = _entity_state(hass, "sensor", "temp_TETHC--1")
    assert float(temp.state) == 25.0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_grid_down_marks_binary_sensor_off(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data={"host": "192.168.91.1", CONF_GW_PWD: "secret"},
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
        data={"host": "192.168.91.1", CONF_GW_PWD: "secret"},
    )
    entry.add_to_hass(hass)

    pw = make_fake_pw()
    pw.is_connected.return_value = False

    with patch(CONNECT_TARGET, return_value=pw):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
