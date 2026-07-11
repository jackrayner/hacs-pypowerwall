# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [HACS](https://hacs.xyz/) custom integration for Home Assistant. It wraps [pypowerwall](https://github.com/jasonacox/pypowerwall) so Home Assistant polls a Tesla Powerwall gateway directly in TEDAPI (local) mode — no MQTT broker in the loop. Domain: `pypowerwall`.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Test
python3 -m pytest
python3 -m pytest tests/test_setup.py -v   # single file
```

`requirements-dev.txt` pulls in `pytest-homeassistant-custom-component`, which installs a full `homeassistant` core package for the `hass` test fixture, `MockConfigEntry`, etc. — a large, slow install, but the standard way to test HA custom components.

`pytest.ini` sets `pythonpath = .` (so `custom_components.pypowerwall...` imports work from `tests/`) and `asyncio_mode = auto` (all `async def test_*` run without `@pytest.mark.asyncio`). `tests/` has no `__init__.py`, so pytest puts it on `sys.path` directly — import the shared test helper as `from conftest import ...`, not a relative `from .conftest import ...`.

There is no way to run this integration standalone outside Home Assistant — it only loads inside HA (or the `hass` test fixture), since `coordinator.py`, `config_flow.py`, etc. import `homeassistant.*`.

## Structure

- `custom_components/pypowerwall/`
  - `manifest.json` — HA metadata; declares `pypowerwall` as the only runtime requirement (HA installs it itself from this, independent of `requirements.txt`).
  - `const.py` — `DOMAIN`, config keys, default scan interval.
  - `config_flow.py` — UI setup step (host + gateway password), validates the connection and uses the gateway's DIN as the config entry's `unique_id` (so re-adding the same gateway aborts as "already configured"). Also an options flow for scan interval.
  - `coordinator.py` — `PowerwallDataUpdateCoordinator`, a `DataUpdateCoordinator` that polls a synchronous `pypowerwall.Powerwall` client via `hass.async_add_executor_job` (pypowerwall has no async API) and maps its methods onto a `PowerwallData` dataclass. `async_connect_powerwall()` does the initial connect + `is_connected()` check, raising `ConfigEntryNotReady` on failure so HA retries setup.
  - `entity.py` — `PowerwallEntity` base class; builds shared `device_info` (one HA device per gateway, keyed by DIN) so every entity below groups under it.
  - `sensor.py` — static sensors declared as `PowerwallSensorDescription` (a `SensorEntityDescription` + `value_fn`), plus per-battery-pack temperature sensors added dynamically as new devices show up in `coordinator.data.temps` (tracked via a `known_temp_devices` set and a coordinator listener, since the gateway doesn't report how many battery packs exist up front).
  - `binary_sensor.py` — one `connectivity` binary sensor derived from grid status (`UP` → on).
  - `strings.json` / `translations/en.json` — config flow + entity name text; kept identical, `en.json` is a plain copy of `strings.json` (HACS/HA convention — `strings.json` is the source of truth, `translations/en.json` is what ships).
- `hacs.json` — HACS repository metadata (minimum HA version, etc.).
- `tests/`
  - `conftest.py` — `make_fake_pw(**overrides)` builds a fully-stubbed `pypowerwall.Powerwall` `MagicMock`. It must stub *every* method the coordinator calls, not just the ones a given test cares about: completing the config flow triggers a real entry setup, and any unstubbed method returns an auto-generated `MagicMock` that Home Assistant's storage layer then fails to JSON-serialize when it persists the device/entity registry.
  - `test_coordinator.py` — pure unit tests of `_fetch_data()`'s pypowerwall → `PowerwallData` mapping; no `hass` fixture needed.
  - `test_config_flow.py`, `test_setup.py` — exercise the flow and full entry setup/unload against the `hass` fixture, patching `pypowerwall.Powerwall` at the `custom_components.pypowerwall.<module>.pypowerwall.Powerwall` path (patching the shared `pypowerwall` module's `Powerwall` attribute affects every module that did `import pypowerwall`, so one patch covers both `config_flow.py`'s validation call and `coordinator.py`'s connection call in the same test).
  - Entities are looked up via the entity registry (`er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)`) rather than by guessing `entity_id` strings, since entity IDs derived from `has_entity_name` + translated names aren't reliably reproducible in a test environment without full translation loading.

## Conventions

- No comments except where a genuine non-obvious constraint exists.
- pypowerwall is synchronous throughout; anything that calls into it from HA code must go through `hass.async_add_executor_job`.
- `requirements.txt` — runtime only (just `pypowerwall`, matching `manifest.json`). `requirements-dev.txt` adds test deps via `-r requirements.txt`. Keep this split.
- The live gateway at `192.168.91.1` (site "Home") is real hardware — prefer stubbing `pypowerwall.Powerwall` in tests over touching it directly.
