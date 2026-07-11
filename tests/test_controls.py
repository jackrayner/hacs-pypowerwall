from unittest.mock import patch

from conftest import DIN, make_fake_pw
from homeassistant.core import HomeAssistant
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


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{DIN}_{unique_id}")
    assert entity_id is not None, f"no {platform} entity registered for unique_id {unique_id}"
    return entity_id


async def _setup_entry(hass: HomeAssistant, pw) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(CONNECT_TARGET, return_value=pw):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_reserve_number_reflects_state_and_writes_through(hass: HomeAssistant) -> None:
    pw = make_fake_pw(battery_reserve=20.0)
    await _setup_entry(hass, pw)

    entity_id = _entity_id(hass, "number", "battery_reserve")
    state = hass.states.get(entity_id)
    assert float(state.state) == 20.0

    pw.get_reserve.return_value = 35.0
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": 35}, blocking=True
    )
    await hass.async_block_till_done()

    pw.set_reserve.assert_called_once_with(35)
    state = hass.states.get(entity_id)
    assert float(state.state) == 35.0


async def test_mode_select_reflects_state_and_writes_through(hass: HomeAssistant) -> None:
    pw = make_fake_pw(battery_mode="self_consumption")
    await _setup_entry(hass, pw)

    entity_id = _entity_id(hass, "select", "battery_mode")
    state = hass.states.get(entity_id)
    assert state.state == "self_consumption"
    assert set(state.attributes["options"]) == {"self_consumption", "backup", "autonomous"}

    pw.get_mode.return_value = "backup"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": "backup"}, blocking=True
    )
    await hass.async_block_till_done()

    pw.set_mode.assert_called_once_with("backup")
    state = hass.states.get(entity_id)
    assert state.state == "backup"
