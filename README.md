# hacs-pypowerwall

A [HACS](https://hacs.xyz/) custom integration for Home Assistant that connects to a Tesla Powerwall gateway using [pypowerwall](https://github.com/jasonacox/pypowerwall) (TEDAPI/local mode). No MQTT broker required — Home Assistant polls the gateway directly and exposes battery, grid, solar, and home power as native entities.

## Installation

### Via HACS

1. HACS → Integrations → ⋮ → Custom repositories → add this repo URL, category "Integration".
2. Install "Tesla Powerwall (pypowerwall)" and restart Home Assistant.

### Manual

Copy `custom_components/pypowerwall/` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

Settings → Devices & Services → Add Integration → "Tesla Powerwall (pypowerwall)".

You'll need:

- **Host** — hostname or IP of the Powerwall gateway (e.g. `192.168.91.1`)
- **Gateway password** — the full Wi-Fi password printed on the gateway's QR sticker

The integration connects in full TEDAPI mode (mode 4), the same mode used by [pypowerwall](https://github.com/jasonacox/pypowerwall)'s `gw_pwd` parameter. Poll interval defaults to 5s and is configurable afterward via the integration's Options.

## Entities

| Entity | Platform | Notes |
| --- | --- | --- |
| Battery level | sensor | `%`, from customer API scale |
| Battery level (Tesla app) | sensor | `%`, app-scaled value |
| Battery reserve | sensor | `%` |
| Battery mode | sensor | |
| Backup time remaining | sensor | hours |
| Grid power | sensor | W |
| Solar power | sensor | W |
| Battery power | sensor | W |
| Home power | sensor | W |
| Grid status | sensor | `UP` / `DOWN` / `SYNCING` |
| Grid connected | binary_sensor | connectivity, derived from grid status |
| Active alerts | sensor | count of active alerts |
| Firmware version | sensor | diagnostic |
| Uptime | sensor | diagnostic, seconds |
| `<device>` temperature | sensor | one per battery pack reported by `vitals()`, added dynamically |

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

python3 -m pytest
```

`requirements-dev.txt` adds `pytest` and `pytest-homeassistant-custom-component` (a full Home Assistant core install used only for testing) on top of `requirements.txt`.

## Project structure

```
custom_components/pypowerwall/
├── manifest.json         # HA integration metadata, pypowerwall dependency
├── const.py
├── config_flow.py        # UI setup (host + gateway password) and options (scan interval)
├── coordinator.py         # DataUpdateCoordinator polling pypowerwall.Powerwall
├── entity.py               # shared device_info base entity
├── sensor.py
├── binary_sensor.py
├── strings.json / translations/en.json
hacs.json
tests/
├── conftest.py            # make_fake_pw() stub + enable_custom_integrations fixture
├── test_coordinator.py    # pure unit tests of the pypowerwall -> PowerwallData mapping
├── test_config_flow.py
└── test_setup.py          # full entry setup/unload against a stubbed Powerwall client
```
