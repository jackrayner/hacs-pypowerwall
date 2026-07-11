from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from conftest import DIN, make_fake_pw
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.pypowerwall.const import (
    CONF_CONN_TYPE,
    CONF_GW_PWD,
    CONN_TYPE_TEDAPI,
    DOMAIN,
)

CONNECT_TARGET = "custom_components.pypowerwall.coordinator.pypowerwall.Powerwall"
UTCNOW_TARGET = "custom_components.pypowerwall.sensor.dt_util.utcnow"
ENTRY_DATA = {CONF_CONN_TYPE: CONN_TYPE_TEDAPI, "host": "192.168.91.1", CONF_GW_PWD: "secret"}

ENERGY_INTEGRATION_KEYS = [
    "battery_import_energy",
    "battery_export_energy",
    "grid_import_energy",
    "grid_export_energy",
    "home_energy",
]


def _entity_id(hass: HomeAssistant, unique_id: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DIN}_{unique_id}")
    assert entity_id is not None, f"no sensor entity registered for unique_id {unique_id}"
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


async def _enable_and_reload(
    hass: HomeAssistant, entry: MockConfigEntry, pw, entity_id: str
) -> None:
    registry = er.async_get(hass)
    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    with patch(CONNECT_TARGET, return_value=pw):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()


async def test_energy_integration_sensors_registered_but_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    pw = make_fake_pw()
    await _setup_entry(hass, pw)

    registry = er.async_get(hass)
    for key in ENERGY_INTEGRATION_KEYS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DIN}_{key}")
        assert entity_id is not None, f"no registry entry for {key}"
        entity_entry = registry.async_get(entity_id)
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        # Disabled entities aren't instantiated by the platform, so they have no state.
        assert hass.states.get(entity_id) is None


async def test_home_energy_accumulates_via_trapezoidal_integration(hass: HomeAssistant) -> None:
    pw = make_fake_pw(home_power=1000.0)
    entry = await _setup_entry(hass, pw)

    entity_id = _entity_id(hass, "home_energy")
    await _enable_and_reload(hass, entry, pw, entity_id)

    # Freshly (re-)added entity with nothing restored starts at 0.
    assert float(hass.states.get(entity_id).state) == 0.0

    t0 = datetime(2026, 1, 1, tzinfo=UTC)

    # First post-enable refresh has no previous sample yet, so it only records
    # a baseline -- no delta should be added.
    pw.home.return_value = 1000.0
    with patch(UTCNOW_TARGET, return_value=t0):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 0.0

    # Power ramps from 1000W to 3000W over exactly 1 hour: trapezoidal average
    # is 2000W for 1h = 2.0 kWh.
    pw.home.return_value = 3000.0
    with patch(UTCNOW_TARGET, return_value=t0 + timedelta(hours=1)):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 2.0

    # Power holds steady at 3000W for another 30 minutes: 3000W * 0.5h = 1.5 kWh,
    # added on top of the running total (2.0 + 1.5 = 3.5).
    pw.home.return_value = 3000.0
    with patch(UTCNOW_TARGET, return_value=t0 + timedelta(hours=1, minutes=30)):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 3.5


async def test_energy_integration_survives_restart_via_restore_state(hass: HomeAssistant) -> None:
    pw = make_fake_pw(home_power=500.0)
    entry = await _setup_entry(hass, pw)

    entity_id = _entity_id(hass, "home_energy")
    await _enable_and_reload(hass, entry, pw, entity_id)

    with patch(UTCNOW_TARGET, return_value=datetime(2026, 1, 1, tzinfo=UTC)):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    # Simulate Home Assistant restarting: unload, seed the restore-state cache
    # with a prior running total, then set the entry up again.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    mock_restore_cache(hass, [State(entity_id, "12.345")])

    with patch(CONNECT_TARGET, return_value=pw):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Restored before any new coordinator update fires.
    assert float(hass.states.get(entity_id).state) == 12.345


async def test_missing_source_reading_is_skipped_not_reset(hass: HomeAssistant) -> None:
    """A poll with a missing (None) source reading adds no delta and doesn't
    overwrite the last known valid sample -- it's simply skipped. The next
    valid reading then integrates from that last known sample, spanning the
    full elapsed time including the gap, rather than treating the gap as a
    zero-power interval or resetting the baseline.
    """
    pw = make_fake_pw(grid_power=100.0)
    entry = await _setup_entry(hass, pw)

    entity_id = _entity_id(hass, "grid_import_energy")
    await _enable_and_reload(hass, entry, pw, entity_id)

    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    pw.grid.return_value = 1000.0
    with patch(UTCNOW_TARGET, return_value=t0):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    # A poll that fails to report grid power (None) is skipped: no delta, and
    # the previous (1000W @ t0) sample is left in place rather than cleared.
    pw.grid.return_value = None
    with patch(UTCNOW_TARGET, return_value=t0 + timedelta(hours=1)):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 0.0

    # Once readings resume, integration bridges from the last valid sample
    # (1000W @ t0) to the new one (3000W @ t0+2h): (1000+3000)/2 * 2h = 4 kWh.
    pw.grid.return_value = 3000.0
    with patch(UTCNOW_TARGET, return_value=t0 + timedelta(hours=2)):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 4.0
