from unittest.mock import patch

from conftest import DIN, make_fake_pw
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pypowerwall.const import (
    CONF_AUTHPATH,
    CONF_CONN_TYPE,
    CONF_GW_PWD,
    CONF_RSA_KEY_PATH,
    CONN_TYPE_CLOUD,
    CONN_TYPE_TEDAPI,
    CONN_TYPE_TEDAPI_V1R,
    DOMAIN,
)

CONNECT_TARGET = "custom_components.pypowerwall.coordinator.pypowerwall.Powerwall"
ENTRY_DATA = {CONF_CONN_TYPE: CONN_TYPE_TEDAPI, "host": "192.168.91.1", CONF_GW_PWD: "secret"}
CLOUD_ENTRY_DATA = {CONF_CONN_TYPE: CONN_TYPE_CLOUD, CONF_AUTHPATH: "/auth"}
V1R_ENTRY_DATA = {
    CONF_CONN_TYPE: CONN_TYPE_TEDAPI_V1R,
    "host": "192.168.91.1",
    CONF_GW_PWD: "secret",
    CONF_RSA_KEY_PATH: "/key.pem",
}


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{DIN}_{unique_id}")
    assert entity_id is not None, f"no {platform} entity registered for unique_id {unique_id}"
    return entity_id


async def _setup_entry(
    hass: HomeAssistant, pw, data: dict[str, object] = ENTRY_DATA
) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DIN, data=data)
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


async def test_tedapi_entry_has_no_cloud_only_entities_or_v1r_services(
    hass: HomeAssistant,
) -> None:
    """Local/TEDAPI mode doesn't support grid charging/export or v1r backup actions."""
    pw = make_fake_pw()
    await _setup_entry(hass, pw)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("switch", DOMAIN, f"{DIN}_grid_charging") is None
    assert registry.async_get_entity_id("select", DOMAIN, f"{DIN}_grid_export") is None
    assert not hass.services.has_service(DOMAIN, "schedule_max_backup")
    assert not hass.services.has_service(DOMAIN, "cancel_max_backup")

    # go_off_grid/reconnect_grid aren't yet implemented by any pypowerwall backend, so
    # these buttons are intentionally ungated -- present for every connection type.
    assert registry.async_get_entity_id("button", DOMAIN, f"{DIN}_reconnect_grid") is not None
    assert registry.async_get_entity_id("button", DOMAIN, f"{DIN}_go_off_grid") is not None


async def test_grid_charging_switch_reflects_state_and_writes_through(
    hass: HomeAssistant,
) -> None:
    pw = make_fake_pw(grid_charging=True)
    await _setup_entry(hass, pw, CLOUD_ENTRY_DATA)

    entity_id = _entity_id(hass, "switch", "grid_charging")
    state = hass.states.get(entity_id)
    assert state.state == "on"

    pw.get_grid_charging.return_value = False
    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()

    pw.set_grid_charging.assert_called_once_with(False)
    state = hass.states.get(entity_id)
    assert state.state == "off"


async def test_grid_export_select_reflects_state_and_writes_through(
    hass: HomeAssistant,
) -> None:
    pw = make_fake_pw(grid_export="battery_ok")
    await _setup_entry(hass, pw, CLOUD_ENTRY_DATA)

    entity_id = _entity_id(hass, "select", "grid_export")
    state = hass.states.get(entity_id)
    assert state.state == "battery_ok"
    assert set(state.attributes["options"]) == {"battery_ok", "pv_only", "never"}

    pw.get_grid_export.return_value = "pv_only"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": "pv_only"}, blocking=True
    )
    await hass.async_block_till_done()

    pw.set_grid_export.assert_called_once_with("pv_only")
    state = hass.states.get(entity_id)
    assert state.state == "pv_only"


async def test_cloud_entry_has_no_v1r_services(hass: HomeAssistant) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw, CLOUD_ENTRY_DATA)

    assert not hass.services.has_service(DOMAIN, "schedule_max_backup")
    assert not hass.services.has_service(DOMAIN, "cancel_max_backup")


async def test_v1r_entry_registers_and_calls_max_backup_services(hass: HomeAssistant) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw, V1R_ENTRY_DATA)

    assert hass.services.has_service(DOMAIN, "schedule_max_backup")
    assert hass.services.has_service(DOMAIN, "cancel_max_backup")

    await hass.services.async_call(
        DOMAIN, "schedule_max_backup", {"duration_seconds": 3600}, blocking=True
    )
    await hass.async_block_till_done()
    pw.schedule_max_backup.assert_called_once_with(3600)

    await hass.services.async_call(DOMAIN, "cancel_max_backup", {}, blocking=True)
    await hass.async_block_till_done()
    pw.cancel_max_backup.assert_called_once_with()


async def test_schedule_max_backup_defaults_duration_to_7200(hass: HomeAssistant) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw, V1R_ENTRY_DATA)

    await hass.services.async_call(DOMAIN, "schedule_max_backup", {}, blocking=True)
    await hass.async_block_till_done()

    pw.schedule_max_backup.assert_called_once_with(7200)


async def test_v1r_entry_has_no_cloud_only_entities(hass: HomeAssistant) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw, V1R_ENTRY_DATA)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("switch", DOMAIN, f"{DIN}_grid_charging") is None
    assert registry.async_get_entity_id("select", DOMAIN, f"{DIN}_grid_export") is None


async def test_reconnect_grid_button_calls_pw(hass: HomeAssistant) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw)

    entity_id = _entity_id(hass, "button", "reconnect_grid")
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()

    pw.reconnect_grid.assert_called_once_with()


async def test_go_off_grid_button_disabled_by_default(hass: HomeAssistant) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("button", DOMAIN, f"{DIN}_go_off_grid")
    assert entity_id is not None
    entity_entry = registry.async_get(entity_id)
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    # Disabled entities aren't instantiated by the platform, so they have no state.
    assert hass.states.get(entity_id) is None


async def test_go_off_grid_button_calls_pw_with_confirm_when_enabled(
    hass: HomeAssistant,
) -> None:
    pw = make_fake_pw()
    entry = await _setup_entry(hass, pw)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("button", DOMAIN, f"{DIN}_go_off_grid")
    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    with patch(CONNECT_TARGET, return_value=pw):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()

    pw.go_off_grid.assert_called_once_with(True)
