"""Constants for the pypowerwall integration."""

DOMAIN = "pypowerwall"

CONF_CONN_TYPE = "conn_type"
CONF_GW_PWD = "gw_pwd"
CONF_AUTHPATH = "authpath"
CONF_SITEID = "siteid"
CONF_RSA_KEY_PATH = "rsa_key_path"
CONF_WIFI_HOST = "wifi_host"

# Connection types, each mapping to a distinct pypowerwall.Powerwall() call shape.
# See coordinator.build_powerwall_kwargs() for exactly which kwargs each one sends.
CONN_TYPE_LOCAL = "local"
CONN_TYPE_TEDAPI = "tedapi"
CONN_TYPE_HYBRID = "hybrid"
CONN_TYPE_TEDAPI_V1R = "tedapi_v1r"
CONN_TYPE_CLOUD = "cloud"
CONN_TYPE_FLEETAPI = "fleetapi"

# Cloud and FleetAPI modes authenticate via a pre-existing token/config cache file
# (produced by `python -m pypowerwall setup` / `python -m pypowerwall.fleetapi setup`
# respectively) rather than credentials a form can collect directly; v1r LAN mode
# similarly needs a pre-registered RSA key file. These three all take a filesystem
# path rather than inline credentials.
FILE_BASED_CONN_TYPES = (CONN_TYPE_CLOUD, CONN_TYPE_FLEETAPI, CONN_TYPE_TEDAPI_V1R)

DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 2

MANUFACTURER = "Tesla"
