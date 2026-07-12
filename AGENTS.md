# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What this is

A [HACS](https://hacs.xyz/) custom integration for Home Assistant. It wraps [pypowerwall](https://github.com/jasonacox/pypowerwall) so Home Assistant polls a Tesla Powerwall directly — no MQTT broker in the loop. Domain: `pypowerwall`. Supports all six of pypowerwall's connection modes (local TEDAPI, customer login, hybrid, cloud, FleetAPI, TEDAPI v1r LAN), selected via a config-flow menu.

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

- `custom_components/pypowerwall/` — the integration itself (manifest, config flow, coordinator, all entity platforms, brand assets, translations). See [`custom_components/pypowerwall/AGENTS.md`](./custom_components/pypowerwall/AGENTS.md) for file-by-file rationale.
- `hacs.json` — HACS repository metadata (minimum HA version, etc.).
- `tests/` — pytest suite against `pytest-homeassistant-custom-component`. See [`tests/AGENTS.md`](./tests/AGENTS.md) for how the mocking and test architecture work.

## Releases

Versioning is automated by [release-please](https://github.com/googleapis/release-please) (`.github/workflows/release-please.yml`, config in `release-please-config.json` / `.release-please-manifest.json`). It parses [Conventional Commits](https://www.conventionalcommits.org/) on `main` — **commit messages must use `feat:`/`fix:`/`feat!:`/`BREAKING CHANGE:`/etc. prefixes for this to work**; anything else (like most of this repo's history before the release-please setup) doesn't trigger a version bump. On every push to `main` it opens or updates a single running "chore(main): release X.Y.Z" PR with the computed version and changelog; merging that PR bumps `custom_components/pypowerwall/manifest.json`'s `version` field (via the `extra-files` jsonpath config) and creates the matching git tag + GitHub Release in the same commit. Tags are created without a `v` prefix (`include-v-in-tag: false`) so the tag string is always identical to the manifest version — this matters because HACS release detection compares the two.

## Conventions

- No comments except where a genuine non-obvious constraint exists.
- pypowerwall is synchronous throughout; anything that calls into it from HA code must go through `hass.async_add_executor_job`.
- `requirements.txt` — runtime only (just `pypowerwall`, matching `manifest.json`). `requirements-dev.txt` adds test deps via `-r requirements.txt`. Keep this split.
- The live gateway at `192.168.91.1` (site "Home") is real hardware — prefer stubbing `pypowerwall.Powerwall` in tests over touching it directly.
- After editing any `.md` file, run markdownlint to check formatting consistency before committing — rules live in `.markdownlint.jsonc` (see its comments for why `MD013`/`MD033` are disabled). If Node/`npx` is available, run it with the same globs the `Lint` workflow uses (`.github/workflows/lint.yml`'s `markdownlint` job — notably excluding `CHANGELOG.md`, which is release-please-generated and not meant to satisfy hand-authored formatting rules). If Node isn't available locally (it isn't in every dev environment), push and check the `markdownlint` job in CI instead — don't assume a doc edit is clean without one or the other.
