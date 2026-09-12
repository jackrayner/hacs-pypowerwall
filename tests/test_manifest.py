import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
MANIFEST_PATH = ROOT_DIR / "custom_components" / "pypowerwall" / "manifest.json"
REQUIREMENTS_PATH = ROOT_DIR / "requirements.txt"


def _manifest_pypowerwall_version() -> str:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    for requirement in manifest["requirements"]:
        match = re.match(r"pypowerwall==(.+)", requirement)
        if match:
            return match.group(1)

    raise AssertionError(f"No pinned pypowerwall requirement found in {MANIFEST_PATH}")


def _requirements_txt_pypowerwall_version() -> str:
    with open(REQUIREMENTS_PATH, encoding="utf-8") as f:
        for line in f:
            match = re.match(r"pypowerwall==(.+)", line.strip())
            if match:
                return match.group(1)

    raise AssertionError(f"No pinned pypowerwall requirement found in {REQUIREMENTS_PATH}")


def test_manifest_pypowerwall_version_matches_requirements_txt():
    """manifest.json's pinned pypowerwall version is what Home Assistant
    actually installs for end users; requirements.txt's pin is what CI/dev
    installs and tests against. Dependabot can only bump requirements.txt
    (its pip ecosystem parser has no notion of a version pin embedded in
    manifest.json's `requirements` array), so nothing keeps these in sync
    automatically -- if they drift, production users silently run a
    different pypowerwall version than the one the test suite validates.
    """
    manifest_version = _manifest_pypowerwall_version()
    requirements_version = _requirements_txt_pypowerwall_version()

    assert manifest_version == requirements_version, (
        f"pypowerwall version mismatch: {MANIFEST_PATH} pins "
        f"{manifest_version!r} but {REQUIREMENTS_PATH} pins "
        f"{requirements_version!r}. Update manifest.json's requirements "
        "entry to match (Dependabot only bumps requirements.txt)."
    )
