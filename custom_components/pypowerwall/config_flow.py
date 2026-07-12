"""Config flow for the pypowerwall integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

import pypowerwall

from .const import (
    CONF_AUTHPATH,
    CONF_CONN_TYPE,
    CONF_GW_PWD,
    CONF_RSA_KEY_PATH,
    CONF_SITEID,
    CONF_WIFI_HOST,
    CONN_TYPE_CLOUD,
    CONN_TYPE_FLEETAPI,
    CONN_TYPE_HYBRID,
    CONN_TYPE_LOCAL,
    CONN_TYPE_TEDAPI,
    CONN_TYPE_TEDAPI_V1R,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_CLOUD,
    DOMAIN,
    GRID_CONTROL_CONN_TYPES,
    MIN_SCAN_INTERVAL,
)
from .coordinator import build_powerwall_kwargs

_LOGGER = logging.getLogger(__name__)

STEP_LOCAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_TEDAPI_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_GW_PWD): str,
    }
)

STEP_HYBRID_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_GW_PWD): str,
    }
)

STEP_TEDAPI_V1R_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_GW_PWD): str,
        vol.Required(CONF_RSA_KEY_PATH): str,
        vol.Optional(CONF_WIFI_HOST): str,
    }
)

STEP_CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTHPATH): str,
        vol.Optional(CONF_SITEID): str,
    }
)

STEP_FLEETAPI_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTHPATH): str,
        vol.Optional(CONF_SITEID): str,
    }
)

# Menu order: cheapest-to-set-up modes first, the two file-based advanced modes last.
MENU_OPTIONS = [
    CONN_TYPE_TEDAPI,
    CONN_TYPE_HYBRID,
    CONN_TYPE_LOCAL,
    CONN_TYPE_CLOUD,
    CONN_TYPE_FLEETAPI,
    CONN_TYPE_TEDAPI_V1R,
]


class PowerwallConnectionError(Exception):
    """Raised when the Powerwall gateway cannot be reached or authenticated."""


def _connect_and_get_info(conn_type: str, data: dict[str, Any]) -> tuple[str, str | None]:
    """Connect to the gateway and return (din, site_name), raising on any failure."""
    pw = pypowerwall.Powerwall(**build_powerwall_kwargs(conn_type, data))
    if not pw.is_connected():
        raise PowerwallConnectionError(f"Unable to connect to Powerwall ({conn_type} mode)")
    din = pw.din()
    if not din:
        raise PowerwallConnectionError(f"Connected ({conn_type} mode) but could not read a DIN")
    return din, pw.site_name()


async def _validate_input(
    hass: HomeAssistant, conn_type: str, data: dict[str, Any]
) -> tuple[str, str | None]:
    """Validate the user input, returning (din, site_name)."""
    return await hass.async_add_executor_job(_connect_and_get_info, conn_type, data)


class PypowerwallConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pypowerwall."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user pick which pypowerwall connection mode to set up."""
        return self.async_show_menu(step_id="user", menu_options=MENU_OPTIONS)

    async def _async_step_connection(
        self, conn_type: str, schema: vol.Schema, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Shared validate/create logic for every connection-type step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {CONF_CONN_TYPE: conn_type, **user_input}
            try:
                din, site_name = await _validate_input(self.hass, conn_type, data)
            except PowerwallConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surface unexpected errors as a generic failure
                _LOGGER.exception("Unexpected error validating Powerwall connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(din)
                self._abort_if_unique_id_configured()
                title = data.get(CONF_HOST) or site_name or f"Powerwall ({conn_type})"
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(step_id=conn_type, data_schema=schema, errors=errors)

    async def async_step_tedapi(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """TEDAPI full mode: host + gateway QR password only."""
        return await self._async_step_connection(CONN_TYPE_TEDAPI, STEP_TEDAPI_SCHEMA, user_input)

    async def async_step_hybrid(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Hybrid mode: customer local login plus TEDAPI for supplemental vitals."""
        return await self._async_step_connection(CONN_TYPE_HYBRID, STEP_HYBRID_SCHEMA, user_input)

    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Local customer login mode (Customer Login must be enabled on the gateway)."""
        return await self._async_step_connection(CONN_TYPE_LOCAL, STEP_LOCAL_SCHEMA, user_input)

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Cloud mode: reuses a token cache produced by `python -m pypowerwall setup`."""
        return await self._async_step_connection(CONN_TYPE_CLOUD, STEP_CLOUD_SCHEMA, user_input)

    async def async_step_fleetapi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """FleetAPI mode: reuses a config cache from `python -m pypowerwall.fleetapi setup`."""
        return await self._async_step_connection(
            CONN_TYPE_FLEETAPI, STEP_FLEETAPI_SCHEMA, user_input
        )

    async def async_step_tedapi_v1r(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """TEDAPI v1r LAN mode: requires an RSA key from `python -m pypowerwall register`."""
        return await self._async_step_connection(
            CONN_TYPE_TEDAPI_V1R, STEP_TEDAPI_V1R_SCHEMA, user_input
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

        default_scan_interval = (
            DEFAULT_SCAN_INTERVAL_CLOUD
            if self.config_entry.data[CONF_CONN_TYPE] in GRID_CONTROL_CONN_TYPES
            else DEFAULT_SCAN_INTERVAL
        )
        current = self.config_entry.options.get("scan_interval", default_scan_interval)
        schema = vol.Schema(
            {
                vol.Required("scan_interval", default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL, max=300, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
