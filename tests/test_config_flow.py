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
