"""Config flow for the pypowerwall integration."""

from __future__ import annotations

import logging
from typing import Any

import pypowerwall
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .const import CONF_GW_PWD, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_GW_PWD): str,
    }
)


class PowerwallConnectionError(Exception):
    """Raised when the Powerwall gateway cannot be reached or authenticated."""


def _connect_and_get_din(host: str, gw_pwd: str) -> str:
    """Connect to the gateway and return its DIN, raising on any failure."""
    pw = pypowerwall.Powerwall(host, gw_pwd=gw_pwd)
    if not pw.is_connected():
        raise PowerwallConnectionError(f"Unable to connect to Powerwall at {host}")
    din = pw.din()
    if not din:
        raise PowerwallConnectionError(f"Connected to {host} but could not read a DIN")
    return din


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input, returning the gateway DIN to use as a unique ID."""
    return await hass.async_add_executor_job(_connect_and_get_din, data[CONF_HOST], data[CONF_GW_PWD])


class PypowerwallConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pypowerwall."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                din = await _validate_input(self.hass, user_input)
            except PowerwallConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surface unexpected errors as a generic failure
                _LOGGER.exception("Unexpected error validating Powerwall connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(din)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return PypowerwallOptionsFlow()


class PypowerwallOptionsFlow(OptionsFlow):
    """Handle options for pypowerwall (scan interval)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            "scan_interval", DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required("scan_interval", default=current): NumberSelector(
                    NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=300, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
