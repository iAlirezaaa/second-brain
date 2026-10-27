#!/usr/bin/env python
"""Zone fence enforcer + promotion validator.

Usage:
  python scripts/zone_check.py --proposals file.json

A proposal {"capture":..., "target": "20_Notes", "approved": false} is rejected
when the target zone is human-owned and the proposal is not approved by the human.
Exit 0 = all proposals legal, exit 1 = violations.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, load_json


def check_proposals(proposals, zones_config):
    zones = zones_config["zones"]
    create_only = set(zones_config.get("agent_create_only_in", []))
    violations = []
    for i, proposal in enumerate(proposals):
        what = proposal.get("capture", f"proposal#{i}")
        target = proposal.get("target", "")
        if target not in zones:
            violations.append(f"{what}: target '{target}' is not a known zone")
        elif target in create_only:
            pass  # agent lands items there freely
        elif not proposal.get("approved"):
            violations.append(
                f"{what}: target '{target}' is human-owned — needs approval (\"approved\": true) "
                f"or a test in tests/ proving the fence works")
    return violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", required=True)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    config = load_json(root / "rules" / "zones.json")
    proposals = load_json(args.proposals)["proposals"]
    violations = check_proposals(proposals, config)
    if violations:
        for violation in violations:
            print(f"REJECTED  {violation}")
        return 1
    print(f"OK — {len(proposals)} proposal(s) pass the zone fence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
