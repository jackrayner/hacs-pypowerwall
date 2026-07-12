# Contributing

Thanks for taking an interest in `hacs-pypowerwall`. This is a small, solo-maintained project, so there's no formal process to wade through — just clone it, make your change, and open a PR. This document covers the practical bits: how to get a dev environment running, how tests and linting work, the shape of the code, and the one convention (commit message prefixes) that actually matters for the automation behind the scenes.

If you want the deep-dive version of any of this — file-by-file rationale, the reasoning behind specific design decisions — see [`AGENTS.md`](./AGENTS.md) and its per-directory companions ([`custom_components/pypowerwall/AGENTS.md`](./custom_components/pypowerwall/AGENTS.md), [`tests/AGENTS.md`](./tests/AGENTS.md)). They were written for an AI coding agent so they're terser and more exhaustive than this doc, but equally valid reading for a human who wants the full picture.

## Getting started

```bash
git clone https://github.com/jackrayner/hacs-pypowerwall.git
cd hacs-pypowerwall
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `pytest` plus `pytest-homeassistant-custom-component`, which in turn installs a full `homeassistant` core package to provide the `hass` test fixture, `MockConfigEntry`, and friends. That's a large, slow install (expect it to take a few minutes and pull down a lot of dependencies) — this is normal and is simply the standard way to test HA custom components, there's no lighter-weight alternative.

`requirements.txt` stays runtime-only (just `pypowerwall`, matching what `manifest.json` declares) and `requirements-dev.txt` layers on top of it via `-r requirements.txt`. If you're adding a dependency, think about which of the two files it actually belongs in.

There's no way to run this integration standalone outside Home Assistant — `coordinator.py`, `config_flow.py`, etc. all import `homeassistant.*`, so it only loads inside a real HA instance or the `hass` test fixture used in tests.

## Running tests

```bash
python3 -m pytest
```

To run a single file (handy while iterating):

```bash
python3 -m pytest tests/test_setup.py -v
```

A quick tour of `tests/`:

- **`conftest.py`** — `make_fake_pw()` builds a fully-stubbed `pypowerwall.Powerwall` double (a `MagicMock` with every method the coordinator calls pre-wired to a sane return value). Tests never talk to real hardware. If you add a call to a new `pypowerwall` method anywhere in the integration, you'll need to stub it here too — an unstubbed method returns an auto-generated `MagicMock`, and completing a config flow in a test triggers a *real* entry setup, so Home Assistant's storage layer will choke trying to JSON-serialize that mock when it persists the device/entity registry. It's an easy failure mode to hit and a one-line fix once you know to look for it.
- **`test_coordinator.py`** — pure unit tests of the pypowerwall → `PowerwallData` mapping, plus coverage of every connection-mode branch in `build_powerwall_kwargs()`. No `hass` fixture needed.
- **`test_config_flow.py`** — walks the config flow menu and exercises one success path per connection type.
- **`test_setup.py`** — full config entry setup/unload against the stubbed client.
- **`test_controls.py`** — drives the writable entities (`number`/`select`) through the real HA service calls, not by calling entity methods directly, and checks both that the underlying `pypowerwall` write method was called correctly *and* that the entity's displayed state updates afterward.

One thing worth knowing if you're writing a new test: entities are looked up via the Home Assistant entity registry (`er.async_get(hass).async_get_entity_id(...)`) rather than by guessing an `entity_id` string. Entity IDs derived from translated names aren't reliably reproducible in a test environment without loading the full translation stack, so the registry lookup is the reliable way to get an entity's actual ID.

## Linting

```bash
ruff check .
ruff format .
```

Configuration lives in `pyproject.toml` — currently the `E`, `F`, `I`, `UP`, and `B` rule sets, targeting Python 3.13, 100-character line length. Please run both before opening a PR; CI will otherwise flag it.

## Architecture, briefly

The integration polls a Tesla Powerwall gateway (or Tesla's cloud, depending on connection mode) and exposes it as native Home Assistant entities. The core thing to understand: `pypowerwall.Powerwall` is a *synchronous* client with no async API, so `coordinator.py`'s `DataUpdateCoordinator` polls it via `hass.async_add_executor_job` rather than awaiting it directly. Anywhere the integration calls into pypowerwall, it has to go through the executor.

`coordinator.py` also has `build_powerwall_kwargs(conn_type, data)`, which is the single place that knows how to turn a config entry's stored data into the right constructor call for each of pypowerwall's six connection modes (local TEDAPI, hybrid, local login, cloud, FleetAPI, TEDAPI v1r LAN). Both `config_flow.py` (to validate a connection during setup) and the coordinator's own connect step call through this function, so adding or adjusting a connection mode only means touching it in one place.

Rough file layout, if you're getting oriented:

- `const.py` — domain, config keys, connection-type identifiers, defaults.
- `config_flow.py` — the connection-type menu and one form per mode, plus the options flow (scan interval).
- `coordinator.py` — polling logic and the per-mode kwargs builder described above.
- `entity.py` — shared `PowerwallEntity` base class, builds the common `device_info`.
- `sensor.py`, `binary_sensor.py`, `number.py`, `select.py` — the entity platforms themselves.

For the full rationale behind each file's design (why certain write methods aren't wired up yet, why the brand icon works the way it does, exactly how the test mocking is layered), see [`custom_components/pypowerwall/AGENTS.md`](./custom_components/pypowerwall/AGENTS.md) and [`tests/AGENTS.md`](./tests/AGENTS.md).

## Adding a new entity

The `number.py` and `select.py` platforms are the simplest examples to copy from — each is one small file with a single entity class. The general pattern:

1. Subclass `PowerwallEntity` alongside the relevant HA entity base class (e.g. `NumberEntity`, `SelectEntity`) — this gets you the shared `device_info` so the entity groups under the right gateway device.
2. Set `_attr_unique_id` following the existing `din`-prefixed convention, e.g. `f"{din}_battery_reserve"`. The DIN comes from `coordinator.config_entry.unique_id` (falling back to `coordinator.data.din`).
3. Set `_attr_translation_key` to a key you'll add to the translation files (next step) rather than hardcoding a `name`.
4. Register the entity in the platform's `async_setup_entry()`.
5. Add a matching entry to `custom_components/pypowerwall/translations/en.json` — that's the sole authoritative English source for this integration. Don't add a `strings.json`: it's a Home Assistant Core-only build-time file that custom integrations never process (the [official i18n docs](https://developers.home-assistant.io/docs/internationalization/custom_integration/) explicitly warn against it), so it would just be dead weight that invites the two files to drift out of sync.
6. That's enough to pass CI — `en.json` is the only file you're required to update. This integration ships translations for every language Home Assistant supports (`custom_components/pypowerwall/translations/`), but `tests/test_translations.py` only checks that a locale file has no *stale* keys (referencing something that doesn't exist in `en.json`), not that it covers every key. Home Assistant falls back to the English string for anything a locale file doesn't define, so a new entity can ship English-only and get translated into the other ~60 languages later without anything breaking. If you do want to add the translation yourself, keep the JSON key structure identical to `en.json`'s and leave proper nouns/protocol names (`TEDAPI`, `FleetAPI`, `RSA`, `Wi-Fi`, `Powerwall`) and the `{device}` placeholder untranslated.
7. Write a test. If your entity performs a write, look at `test_controls.py` for the pattern of driving it through the actual HA service call and asserting both the underlying pypowerwall call and the post-write state.

If the entity wraps a new `pypowerwall.Powerwall` method, remember to add that method to `tests/conftest.py`'s `make_fake_pw()` (see the note under Running Tests above).

## Commit messages

This is the one convention that's easy to get wrong in a way that has real consequences, so it's worth reading carefully even if you skim the rest of this doc.

This repo uses [release-please](https://github.com/googleapis/release-please) (see `.github/workflows/release-please.yml` and `release-please-config.json`) to fully automate versioning and changelogs. It works by parsing commit messages on `main` against the [Conventional Commits](https://www.conventionalcommits.org/) spec, so **your commit message prefix directly determines what happens on release**:

- `feat: ...` — triggers a **minor** version bump.
- `fix: ...` — triggers a **patch** version bump.
- `feat!: ...` / `fix!: ...`, or a `BREAKING CHANGE:` footer in the commit body — triggers a **major** version bump.
- `docs:`, `chore:`, `ci:`, `test:`, `refactor:`, etc. — perfectly good conventions to use, but these are intentionally excluded from version calculations and won't show up as a version bump (though most still appear in the changelog).

Concretely, if you make a real bug fix or add a feature but commit it without a `feat:`/`fix:` prefix, **no version bump happens at all** — release-please simply won't know anything release-worthy occurred, and users won't get the fix until some later commit happens to carry the right prefix and sweeps it in incidentally. Conversely, using `feat!:` when the change isn't actually breaking will cut an unnecessarily major version bump. This project has just one maintainer and no separate release-review step, so the commit prefix is effectively the only signal driving the release process — there's nothing downstream to catch a miscategorized commit before it ships.

When in doubt: if it changes behavior a user would notice, it's `feat:` or `fix:`. If it's docs, tests, tooling, or internal refactoring with no behavior change, use the matching non-bumping prefix.

## Pull requests

A few practical guidelines, gathered from how this repo has actually been worked so far:

- Branch off an up-to-date `main`, e.g. `feat/short-description` or `fix/short-description`.
- Keep PRs to one logical change — easier to review, and it keeps the generated changelog readable.
- Run `python3 -m pytest` and `ruff check . && ruff format --check .` locally before pushing. CI will run the same checks, but catching issues locally saves a round trip.
- Open the PR against `main` via `gh pr create` (or the GitHub UI).
- For the PR description, a short **Summary** section (a few bullet points on what changed and why) plus a **Test plan** checklist (what you ran, what still needs manual verification if anything) is the format this repo has settled into — see recent merged PRs for examples of the level of detail that's useful.

## Releases

Once your PR is merged, you don't need to do anything else — release-please picks it up automatically. It keeps a single running "chore(main): release X.Y.Z" PR open with the version bump and changelog computed from commits since the last release; merging that PR is what actually cuts the tag and GitHub Release. See the `## Releases` section of `AGENTS.md` for the mechanics of how the version gets written into `manifest.json` and why tags don't carry a `v` prefix.
