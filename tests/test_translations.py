import json
from pathlib import Path

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


def test_fr_json_has_full_key_parity_with_en_json():
    """fr.json is a full translation, not a partial override like en-GB.json.

    Every string en.json defines must have a French counterpart, and vice
    versa -- if this drifts (e.g. a new entity/service string lands in
    en.json without a French translation, or a key gets renamed in one file
    but not the other), French users silently see English text instead of
    a translation error, so CI needs to catch it instead of relying on
    someone remembering to update fr.json in the same PR.
    """
    en_keys = _load_keys("en.json")
    fr_keys = _load_keys("fr.json")

    missing_in_fr = en_keys - fr_keys
    extra_in_fr = fr_keys - en_keys

    assert not missing_in_fr, f"fr.json is missing translations for: {sorted(missing_in_fr)}"
    assert not extra_in_fr, (
        f"fr.json has keys not present in en.json (stale after a rename?): {sorted(extra_in_fr)}"
    )


def test_en_gb_json_keys_are_a_subset_of_en_json():
    """en-GB.json is a deliberate PARTIAL override (see AGENTS.md): Home
    Assistant always loads en.json first as a fallback, then merges en-GB.json
    on top per-key, so en-GB.json only needs to contain strings that actually
    differ. It must never contain a key that doesn't exist in en.json --
    that would mean it's referencing a renamed or removed string and would
    never actually be applied.
    """
    en_keys = _load_keys("en.json")
    en_gb_keys = _load_keys("en-GB.json")

    stale_keys = en_gb_keys - en_keys
    assert not stale_keys, (
        f"en-GB.json has keys not present in en.json (stale after a rename?): {sorted(stale_keys)}"
    )
