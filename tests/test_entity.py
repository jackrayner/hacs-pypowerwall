from unittest.mock import patch

from conftest import DIN, make_fake_pw
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pypowerwall.const import (
    CONF_CONN_TYPE,
    CONF_GW_PWD,
    CONN_TYPE_TEDAPI,
    DOMAIN,
)
from custom_components.pypowerwall.entity import PowerwallEntity

CONNECT_TARGET = "custom_components.pypowerwall.coordinator.pypowerwall.Powerwall"
ENTRY_DATA = {CONF_CONN_TYPE: CONN_TYPE_TEDAPI, "host": "192.168.91.1", CONF_GW_PWD: "secret"}


async def test_device_info_reflects_latest_coordinator_data(hass: HomeAssistant) -> None:
    """device_info must be derived live so firmware/site-name changes show up without
    a reload, while the DIN stays fixed for the entity's lifetime.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    pw = make_fake_pw(site_name="Home", version="24.4.0")
    with patch(CONNECT_TARGET, return_value=pw):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    entity = PowerwallEntity(coordinator)

    assert entity.din == DIN
    assert entity.device_info["name"] == "Home"
    assert entity.device_info["sw_version"] == "24.4.0"
    assert entity.device_info["serial_number"] == DIN

    # Simulate a firmware update and a site rename on a later poll.
    pw.site_name.return_value = "Lake House"
    pw.version.return_value = "25.1.0"
    await coordinator.async_refresh()

    assert entity.device_info["name"] == "Lake House"
    assert entity.device_info["sw_version"] == "25.1.0"
    # The DIN identifies the physical gateway and must not change.
    assert entity.device_info["serial_number"] == DIN
    assert entity.din == DIN
