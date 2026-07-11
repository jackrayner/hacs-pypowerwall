from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pypowerwall.const import CONF_GW_PWD, DOMAIN

from conftest import make_fake_pw

# The flow's own validation call and the coordinator's connection call (triggered by
# the automatic setup that follows a successful create_entry) both resolve through
# the same shared `pypowerwall` module attribute, so one patch target covers both.
CONNECT_TARGET = "custom_components.pypowerwall.config_flow.pypowerwall.Powerwall"


async def test_user_flow_success(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.91.1", CONF_GW_PWD: "secret"}
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "192.168.91.1"
    assert result2["data"] == {"host": "192.168.91.1", CONF_GW_PWD: "secret"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw(connected=False)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.91.1", CONF_GW_PWD: "wrong"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_missing_din_is_cannot_connect(hass: HomeAssistant) -> None:
    with patch(CONNECT_TARGET, return_value=make_fake_pw(din=None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.91.1", CONF_GW_PWD: "secret"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1232100-00-E--TG123456789ABC",
        data={"host": "192.168.91.1", CONF_GW_PWD: "secret"},
    ).add_to_hass(hass)

    with patch(CONNECT_TARGET, return_value=make_fake_pw()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.91.1", CONF_GW_PWD: "secret"}
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
