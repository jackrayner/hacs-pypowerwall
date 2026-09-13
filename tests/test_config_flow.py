from unittest.mock import patch

from conftest import DIN, make_fake_pw
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pypowerwall.const import (
    CONF_AUTHPATH,
    CONF_CONN_TYPE,
    CONF_GW_PWD,
    CONF_RSA_KEY_PATH,
    CONN_TYPE_CLOUD,
    CONN_TYPE_FLEETAPI,
    CONN_TYPE_HYBRID,
    CONN_TYPE_LOCAL,
    CONN_TYPE_TEDAPI,
    CONN_TYPE_TEDAPI_V1R,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_CLOUD,
    DOMAIN,
)

# The flow's own validation call and the coordinator's connection call (triggered by
# the automatic setup that follows a successful create_entry) both resolve through
# the same shared `pypowerwall` module attribute, so one patch target covers both.
CONNECT_TARGET = "custom_components.pypowerwall.config_flow.pypowerwall.Powerwall"


async def _start_menu(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _select_menu(hass: HomeAssistant, result, conn_type: str):
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": conn_type}
    )


async def test_menu_shown(hass: HomeAssistant) -> None:
    result = await _start_menu(hass)

    assert result["type"] == "menu"
    assert result["step_id"] == "user"
    assert set(result["menu_options"]) == {
        CONN_TYPE_TEDAPI,
        CONN_TYPE_HYBRID,
        CONN_TYPE_LOCAL,
        CONN_TYPE_CLOUD,
        CONN_TYPE_FLEETAPI,
        CONN_TYPE_TEDAPI_V1R,
    }


async def test_tedapi_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_TEDAPI)
        assert result["type"] == "form"
        assert result["step_id"] == CONN_TYPE_TEDAPI

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.91.1", CONF_GW_PWD: "secret"}
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "192.168.91.1"
    assert result2["data"] == {
        CONF_CONN_TYPE: CONN_TYPE_TEDAPI,
        CONF_HOST: "192.168.91.1",
        CONF_GW_PWD: "secret",
    }


async def test_tedapi_flow_cannot_connect(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw(connected=False)):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_TEDAPI)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.91.1", CONF_GW_PWD: "wrong"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_tedapi_flow_missing_din_is_cannot_connect(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw(din=None)):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_TEDAPI)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.91.1", CONF_GW_PWD: "secret"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_tedapi_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data={CONF_CONN_TYPE: CONN_TYPE_TEDAPI, CONF_HOST: "192.168.91.1", CONF_GW_PWD: "secret"},
    ).add_to_hass(hass)

    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_TEDAPI)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.91.1", CONF_GW_PWD: "secret"}
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_hybrid_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_HYBRID)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.91.1",
                CONF_EMAIL: "owner@example.com",
                CONF_PASSWORD: "customerpw",
                CONF_GW_PWD: "secret",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        CONF_CONN_TYPE: CONN_TYPE_HYBRID,
        CONF_HOST: "192.168.91.1",
        CONF_EMAIL: "owner@example.com",
        CONF_PASSWORD: "customerpw",
        CONF_GW_PWD: "secret",
    }


async def test_local_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_LOCAL)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.91.1",
                CONF_EMAIL: "owner@example.com",
                CONF_PASSWORD: "customerpw",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_CONN_TYPE] == CONN_TYPE_LOCAL


async def test_cloud_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw(site_name="Cloud Site")):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_CLOUD)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AUTHPATH: "/config/pypowerwall"}
        )

    assert result2["type"] == "create_entry"
    # No host in cloud-mode data, so the title falls back to the site name pypowerwall reports.
    assert result2["title"] == "Cloud Site"
    assert result2["data"] == {
        CONF_CONN_TYPE: CONN_TYPE_CLOUD,
        CONF_AUTHPATH: "/config/pypowerwall",
    }


async def test_fleetapi_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_FLEETAPI)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AUTHPATH: "/config/pypowerwall"}
        )

    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_CONN_TYPE] == CONN_TYPE_FLEETAPI


async def test_tedapi_v1r_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await _select_menu(hass, await _start_menu(hass), CONN_TYPE_TEDAPI_V1R)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.91.1",
                CONF_GW_PWD: "secret",
                CONF_RSA_KEY_PATH: "/config/pypowerwall/tedapi_rsa_private.pem",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_CONN_TYPE] == CONN_TYPE_TEDAPI_V1R


def _scan_interval_default(result) -> int:
    schema = result["data_schema"].schema
    (marker,) = (key for key in schema if key == "scan_interval")
    return marker.default()


async def test_options_flow_defaults_to_cloud_interval_for_cloud_entry(
    hass: HomeAssistant,
) -> None:
    """Cloud/FleetAPI entries should default the options form to the slower cloud interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cloud-entry-din",
        data={CONF_CONN_TYPE: CONN_TYPE_CLOUD, CONF_AUTHPATH: "/config/pypowerwall"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert _scan_interval_default(result) == DEFAULT_SCAN_INTERVAL_CLOUD


async def test_options_flow_defaults_to_lan_interval_for_tedapi_entry(
    hass: HomeAssistant,
) -> None:
    """Local/LAN entries should keep defaulting the options form to the fast interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data={CONF_CONN_TYPE: CONN_TYPE_TEDAPI, CONF_HOST: "192.168.91.1", CONF_GW_PWD: "secret"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert _scan_interval_default(result) == DEFAULT_SCAN_INTERVAL


async def test_options_flow_respects_explicit_scan_interval_override(
    hass: HomeAssistant,
) -> None:
    """An explicitly-set scan_interval option should win over the conn-type default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cloud-entry-din-2",
        data={CONF_CONN_TYPE: CONN_TYPE_CLOUD, CONF_AUTHPATH: "/config/pypowerwall"},
        options={"scan_interval": 15},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert _scan_interval_default(result) == 15


def _suggested(result, field: str):
    """The value pre-filled into a form field (HA stores it on the marker's description)."""
    schema = result["data_schema"].schema
    (marker,) = (key for key in schema if key == field)
    return (marker.description or {}).get("suggested_value")


async def _tedapi_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data={CONF_CONN_TYPE: CONN_TYPE_TEDAPI, CONF_HOST: "192.168.91.1", CONF_GW_PWD: "old-pw"},
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_shows_current_values_for_its_conn_type(hass: HomeAssistant) -> None:
    """The form should be the entry's own conn-type schema, pre-filled with its values."""
    entry = await _tedapi_entry(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert set(result["data_schema"].schema) == {CONF_HOST, CONF_GW_PWD}
    assert _suggested(result, CONF_HOST) == "192.168.91.1"
    assert _suggested(result, CONF_GW_PWD) == "old-pw"


async def test_reconfigure_updates_entry_data(hass: HomeAssistant) -> None:
    """A corrected gateway password should be written back to the existing entry."""
    entry = await _tedapi_entry(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.91.1", CONF_GW_PWD: "correct-pw"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_CONN_TYPE: CONN_TYPE_TEDAPI,
        CONF_HOST: "192.168.91.1",
        CONF_GW_PWD: "correct-pw",
    }


async def test_reconfigure_rejects_a_different_gateway(hass: HomeAssistant) -> None:
    """Settings that reach a different DIN must not silently repoint the entry."""
    entry = await _tedapi_entry(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(CONNECT_TARGET, return_value=make_fake_pw(din="9999999-00-F--TGOTHERGATEWAY")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.50", CONF_GW_PWD: "other-pw"}
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "wrong_gateway"
    # The original settings must survive a rejected reconfigure.
    assert entry.data[CONF_HOST] == "192.168.91.1"
    assert entry.data[CONF_GW_PWD] == "old-pw"


async def test_reconfigure_reports_connection_failure_and_keeps_edits(
    hass: HomeAssistant,
) -> None:
    """A failed attempt should re-show the form with the error and the user's input."""
    entry = await _tedapi_entry(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(CONNECT_TARGET, return_value=make_fake_pw(connected=False)):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.91.9", CONF_GW_PWD: "still-wrong"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
    assert _suggested(result2, CONF_HOST) == "192.168.91.9"
    assert entry.data[CONF_GW_PWD] == "old-pw"


async def test_reconfigure_uses_the_schema_of_a_file_based_conn_type(
    hass: HomeAssistant,
) -> None:
    """A FleetAPI entry should get the authpath form, not a TEDAPI one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DIN,
        data={CONF_CONN_TYPE: CONN_TYPE_FLEETAPI, CONF_AUTHPATH: "/config/wrong-dir"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "reconfigure"
    assert CONF_AUTHPATH in result["data_schema"].schema
    assert _suggested(result, CONF_AUTHPATH) == "/config/wrong-dir"
