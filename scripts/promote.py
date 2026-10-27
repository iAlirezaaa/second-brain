#!/usr/bin/env python
"""Promote an approved inbox capture into the human-owned vault.

Usage:
  python scripts/promote.py --proposals P.json --item 00_Inbox/clip.md

Refuses unless the matching proposal is approved. Refuses a destination that
already exists inside a zone listed in agent_edit_never — promoting onto human
content is an edit, and edits there are not the agent's to make. Validates the
fence first, then updates frontmatter, keeps an audit trail in
90_Agent_Output/proposals/promotions.md, then re-checks links.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import candidate_check
from common import find_root, load_json, parse_frontmatter, run_utf8, state_fingerprint
from zone_check import check_zones_config

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def patch_top_level_text(text, updates):
    """Rewrite top-level frontmatter values; append not-yet-present keys before the close."""
    updates = dict(updates)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        # no frontmatter: build a minimal block
        block = ["---"] + [f"{k}: {v}" for k, v in updates.items()] + ["---"]
        return "\n".join(block) + "\n\n" + text, None
    out = ["---"]
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        key = line.partition(":")[0].strip()
        if key in updates:
            out.append(f"{key}: {updates.pop(key)}")
        else:
            out.append(line)
        i += 1
    for key, value in updates.items():
        out.append(f"{key}: {value}")
    if i < len(lines):
        out.append(lines[i])  # closing ---
        out.extend(lines[i + 1:])
    return "\n".join(out) + ("\n" if not text.endswith("\n") else ""), None


def candidate_gate(root, src, fm):
    """A shelf row is a claim, and a claim must be measured on the current tree.

    This is the part the old gate faked: `evaluation.passed` was a hand-written
    boolean, and a checkbox is not a measurement. Returns refusals; empty means
    the row may leave the shelf.
    """
    schema_path = root / "rules" / "candidate.schema.json"
    if not schema_path.is_file():
        return ["rules/candidate.schema.json is missing — the candidate contract cannot be checked"]
    schema = load_json(schema_path)
    problems = candidate_check.check_candidate(
        src, schema, root, state_fingerprint(root), candidate_check.probe_index(root))
    out = ["candidate fails its contract: %s" % problem for problem in problems]
    floor = float((schema.get("promote_floor") or {}).get("confidence", 0.6))
    verdict = str(fm.get("verdict") or "")
    try:
        confidence = float(fm.get("confidence"))
    except (TypeError, ValueError):
        out.append("confidence is missing or not a number — nothing decides how much to trust this")
        confidence = None
    if confidence is not None and confidence < floor:
        out.append("confidence %s is below the promote floor %s" % (confidence, floor))
    if verdict == "keep_base":
        out.append("verdict is keep_base — the honest outcome is to change nothing; "
                   "the row belongs on the shelf, not in the vault")
    elif verdict == "confounded":
        out.append("verdict is confounded — the disagreement gets recorded, not resolved by promoting")
    if str(fm.get("cue") or "").strip() == candidate_check.NO_ENTRY:
        out.append("cue is NO_ENTRY — nothing was learned, so there is nothing to file away")
    return out


def promote(item, proposals_path, root):
    proposals = load_json(proposals_path)["proposals"]
    config = load_json(root / "rules" / "zones.json")
    fence = check_zones_config(config)
    if fence:
        for problem in fence:
            print(f"BAD FENCE: {problem}")
        return 1
    match = next((p for p in proposals if p.get("capture") == item), None)
    if not match:
        print(f"REFUSED: no proposal for {item}")
        return 1
    target = match.get("target", "")
    create_only = set(config.get("agent_create_only_in", []))
    never = set(config.get("agent_edit_never", []))
    if target not in set(k for k in config["zones"].keys()):
        print(f"REFUSED: unknown zone {target}")
        return 1
    if target not in create_only and not match.get("approved"):
        print(f"REFUSED: {target} is human-owned and the proposal is not approved.")
        return 1
    vault = root / "vault-template"
    rel_item = str(item).replace("\\", "/")
    # a capture lives inside the vault; a loop candidate lives on the repo-level shelf
    src = (root if rel_item.startswith("14_CANDIDATES/") else vault) / rel_item
    if not src.is_file():
        print(f"REFUSED: {item} not found in the vault")
        return 1
    src_fm, _src_body = parse_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
    if candidate_check.is_candidate(src_fm):
        problems = candidate_gate(root, src, src_fm)
        if problems:
            for problem in problems:
                print(f"REFUSED: {problem}")
            return 1
    destination = match.get("destination") or f"{target}/{src.name}"
    dest = vault / destination
    if dest.exists() and target in never:
        print(f"REFUSED: {destination} already exists and {target} is in agent_edit_never — "
              f"promoting there would overwrite human content. Pick a new destination and let "
              f"the human merge.")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    fm, _body = parse_frontmatter(text)
    today = datetime.date.today().isoformat()
    updates = {
        "status": "raw" if (fm.get("status") == "inbox" or not fm.get("status")) else fm.get("status"),
        "promoted_by": "human",
        "promoted_on": today,
        "updated": today,
    }
    new_text, _ = patch_top_level_text(text, updates)
    dest.write_text(new_text, encoding="utf-8")
    src.unlink()
    audit = vault / "90_Agent_Output/proposals/promotions.md"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.open("a", encoding="utf-8").write(
        f"- {today}: {item} → {destination} (reason: {match.get('reason', '-')})\n")
    print(f"PROMOTED  {item} → {destination}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--root", default=None, help="repo root override (for tests/examples)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    code = promote(args.item, Path(args.proposals), root)
    if code == 0:  # post-move health check
        result = run_utf8([sys.executable, str(Path(__file__).parent / "link_check.py")])
        print(result.stdout.strip())
        if result.returncode != 0:
            print("WARNING: the vault now has broken links — fix before continuing.")
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
