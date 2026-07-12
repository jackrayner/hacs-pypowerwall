import json
from pathlib import Path

import pytest

TRANSLATIONS_DIR = (
    Path(__file__).parent.parent / "custom_components" / "pypowerwall" / "translations"
)


def _flatten_keys(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            keys |= _flatten_keys(value, f"{path}.")
        else:
            keys.add(path)
    return keys


def _load_keys(filename: str) -> set[str]:
    with open(TRANSLATIONS_DIR / filename, encoding="utf-8") as f:
        return _flatten_keys(json.load(f))


def _other_locale_files() -> list[str]:
    return sorted(p.name for p in TRANSLATIONS_DIR.glob("*.json") if p.name != "en.json")


@pytest.mark.parametrize("filename", _other_locale_files())
def test_locale_file_has_no_stale_keys(filename: str):
    """Every non-English translations/*.json file may be a full translation
    or a partial override (see AGENTS.md) -- Home Assistant always loads
    en.json first as a fallback and merges the selected language on top
    per-key, so a locale file is never required to cover every key, and new
    entities/strings can ship English-only and get translated later without
    breaking anything (missing keys just fall back to English text).

    What a locale file must never do is reference a key that doesn't exist
    in en.json -- that means it's referencing a renamed or removed string
    and would silently never be applied.
    """
    en_keys = _load_keys("en.json")
    locale_keys = _load_keys(filename)

    stale_keys = locale_keys - en_keys
    assert not stale_keys, (
        f"{filename} has keys not present in en.json (stale after a rename?): {sorted(stale_keys)}"
    )
