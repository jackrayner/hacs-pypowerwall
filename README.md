# hacs-pypowerwall

A [HACS](https://hacs.xyz/) custom integration for Home Assistant that connects to a Tesla Powerwall gateway using [pypowerwall](https://github.com/jasonacox/pypowerwall). No MQTT broker required — Home Assistant polls the gateway (or Tesla's cloud) directly and exposes battery, grid, solar, and home power as native entities. Supports every connection mode pypowerwall offers: local TEDAPI, customer login, hybrid, cloud, FleetAPI, and TEDAPI v1r LAN.

## Installation

### Via HACS

1. HACS → Integrations → ⋮ → Custom repositories → add this repo URL, category "Integration".
2. Install "Tesla Powerwall (pypowerwall)" and restart Home Assistant.

### Manual

Copy `custom_components/pypowerwall/` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

Settings → Devices & Services → Add Integration → "Tesla Powerwall (pypowerwall)" → pick a connection type.

Poll interval defaults to 5s and is configurable afterward via the integration's Options, regardless of connection type.

### Connection types

| Type | What it needs | Setup |
| --- | --- | --- |
| **TEDAPI** (recommended) | Gateway host + the Wi-Fi password from the gateway's QR sticker | Nothing else — works out of the box on Powerwall 2, Powerwall+, and Powerwall 3. |
| **Hybrid** | The above, plus a Customer Login email/password | Adds supplemental vitals on top of TEDAPI. Requires Customer Login enabled on the gateway. |
| **Local login** | Gateway host + Customer Login email/password | Requires [Customer Login](https://www.tesla.com/support/energy/powerwall/mobile-app/monitoring-from-home-network) enabled on the gateway first (Tesla app or gateway web UI). |
| **Cloud mode** | A directory containing a `.pypowerwall.auth` file | One-time setup *outside* Home Assistant: run `python -m pypowerwall setup` (or `setup -headless` if you can't open a browser on the machine) to log into your Tesla account and create that file, then point the integration at its directory. |
| **FleetAPI** | A directory containing a `.pypowerwall.fleetapi` file | One-time setup outside Home Assistant: register an app at [developer.tesla.com](https://developer.tesla.com), then run `python -m pypowerwall.fleetapi setup` to complete the OAuth flow and create that file. |
| **TEDAPI v1r LAN** | Gateway host + gateway password + an RSA private key path | One-time setup outside Home Assistant: run `python -m pypowerwall register` to generate and register an RSA-4096 key pair with the gateway (may require briefly power-cycling it to confirm), then point the integration at the resulting `.pem`. Powerwall 3 only. |

The three file-based modes (Cloud, FleetAPI, TEDAPI v1r) authenticate via an artifact pypowerwall's own CLI setup tools produce — Tesla's login flow needs a real browser (or a token you paste in headlessly), so there's no way to complete it from a single Home Assistant form. Run the relevant `setup`/`register` command once, on any machine, then tell the integration where the resulting file lives (it just needs to be readable from wherever Home Assistant runs).

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

### Releases

Versions are cut automatically by [release-please](https://github.com/googleapis/release-please) from [Conventional Commits](https://www.conventionalcommits.org/) on `main` (`feat:` → minor, `fix:` → patch, `feat!:`/`BREAKING CHANGE:` → major). It keeps a running release PR up to date with the changelog and version bump; merging that PR tags the release and updates `manifest.json` automatically. Commits that don't follow the convention don't trigger a release.

## Project structure

```
custom_components/pypowerwall/
├── manifest.json         # HA integration metadata, pypowerwall dependency
├── const.py
├── config_flow.py        # connection-type menu + one form per mode, and options (scan interval)
├── coordinator.py         # DataUpdateCoordinator polling pypowerwall.Powerwall; builds Powerwall() kwargs per mode
├── entity.py               # shared device_info base entity
├── sensor.py
├── binary_sensor.py
├── brand/                 # icon.png / icon@2x.png (HA 2026.3+ reads this directly, no brands-repo PR needed)
├── strings.json / translations/en.json
hacs.json
tests/
├── conftest.py            # make_fake_pw() stub + enable_custom_integrations fixture
├── test_coordinator.py    # pure unit tests: pypowerwall -> PowerwallData mapping, per-mode kwargs building
├── test_config_flow.py    # menu navigation + one success test per connection type
└── test_setup.py          # full entry setup/unload against a stubbed Powerwall client
```
