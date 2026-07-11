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

# set_grid_charging()/get_grid_charging() and set_grid_export()/get_grid_export() require
# Cloud or FleetAPI mode per pypowerwall's own docstrings -- its local/TEDAPI/hybrid
# backends don't implement grid charging/export control at all. Used to gate the
# switch.py and select.py entities that expose them, and the coordinator's polling.
GRID_CONTROL_CONN_TYPES = (CONN_TYPE_CLOUD, CONN_TYPE_FLEETAPI)

DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 2

MANUFACTURER = "Tesla"

# Max backup (storm watch) actions -- momentary, not persistent state, so they're
# exposed as services (registered in __init__.py, v1r LAN mode only) rather than
# entities. See pypowerwall.Powerwall.schedule_max_backup()/cancel_max_backup().
SERVICE_SCHEDULE_MAX_BACKUP = "schedule_max_backup"
SERVICE_CANCEL_MAX_BACKUP = "cancel_max_backup"
ATTR_DURATION_SECONDS = "duration_seconds"
