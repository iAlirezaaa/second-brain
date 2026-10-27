"""Shared fixture for the registry-plane phases: a throwaway vault with real scripts.

`hades.py` anchors its ROOT on its own file, so the only honest way to test the registry is
to run it inside a copy of the machine plane built by the pack's own seeder. That fixture
already exists and already bites -- `15_SYSTEM/scripts/test_hades.py` -- so it is loaded here
instead of being written a second time in a second place.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATTERY = ROOT / "15_SYSTEM" / "scripts" / "test_hades.py"

_spec = importlib.util.spec_from_file_location("hades_battery", str(BATTERY))
battery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(battery)

Vault = battery.Vault
seed_records = battery.seed_records


def seeded():
    """A scratch vault holding the three honest records: a project, an org, a model."""
    vault = Vault()
    seed_records(vault)
    return vault


def hades_json(vault, *args):
    """Parse the JSON a hades command prints, ignoring the trailer lines."""
    _code, out = vault.hades(*args)
    text = out.strip()
    start = text.find("{")
    if start < 0:
        start = text.find("[")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1]), out


def catalog(vault):
    path = vault.root / "15_SYSTEM" / "generated" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))
