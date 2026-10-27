#!/usr/bin/env python
"""Zone fence enforcer + promotion validator.

Usage:
  python scripts/zone_check.py --proposals file.json [--zones rules/zones.json]

A proposal {"capture":..., "target": "20_Notes", "approved": false} is rejected
when the target zone is human-owned and the proposal is not approved by the human.
An {"action": "edit"} into a zone listed in agent_edit_never is rejected even with
approval — the legal path is a new note in 00_Inbox that a human merges.

The fence file is judged first: a rule that names a zone which does not exist, or
that leaves a human-owned zone unprotected, is rejected before any proposal is.
A law nothing enforces is not a law, and a phantom zone protects nothing.

Exit 0 = all proposals legal, exit 1 = violations.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, load_json


def check_zones_config(zones_config):
    """Validate the fence itself. Returns a list of problems; empty means legal."""
    zones = zones_config.get("zones", {})
    problems = []
    if not zones:
        return ["zones.json declares no zones at all"]
    for key in ("agent_create_only_in", "agent_edit_never"):
        for zone in zones_config.get(key, []):
            if zone not in zones:
                problems.append(
                    f"{key} names {zone!r}, which is not a declared zone — the rule can never bind")
    never = set(zones_config.get("agent_edit_never", []))
    for zone, owner in sorted(zones.items()):
        if owner == "human" and zone not in never:
            problems.append(f"zone {zone!r} is human-owned but missing from agent_edit_never")
        if owner in ("agent", "shared") and zone in never:
            problems.append(f"zone {zone!r} is {owner}-owned but listed in agent_edit_never")
    create_only = set(zones_config.get("agent_create_only_in", []))
    if not create_only:
        problems.append("agent_create_only_in is empty — an agent could land nowhere")
    return problems


def check_proposals(proposals, zones_config):
    zones = zones_config["zones"]
    create_only = set(zones_config.get("agent_create_only_in", []))
    never = set(zones_config.get("agent_edit_never", []))
    violations = []
    for i, proposal in enumerate(proposals):
        what = proposal.get("capture", f"proposal#{i}")
        target = proposal.get("target", "")
        action = proposal.get("action", "create")
        if target not in zones:
            violations.append(f"{what}: target '{target}' is not a known zone")
        elif action == "edit" and target in never:
            violations.append(
                f"{what}: editing {target} is never allowed for an agent (agent_edit_never) — "
                f"write a note into 00_Inbox and let the human merge it")
        elif target in create_only:
            pass  # agent lands items there freely
        elif action == "edit":
            if not proposal.get("approved"):
                violations.append(
                    f"{what}: editing '{target}' needs a human approval (\"approved\": true)")
        elif not proposal.get("approved"):
            violations.append(
                f"{what}: target '{target}' is human-owned — needs approval (\"approved\": true) "
                f"or a test in tests/ proving the fence works")
    return violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--zones", help="alternate zones.json, for testing the fence itself")
    args = parser.parse_args()
    root = find_root(Path(__file__))
    config = load_json(Path(args.zones) if args.zones else root / "rules" / "zones.json")
    fence_problems = check_zones_config(config)
    if fence_problems:
        for problem in fence_problems:
            print(f"BAD FENCE  {problem}")
        return 1
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
