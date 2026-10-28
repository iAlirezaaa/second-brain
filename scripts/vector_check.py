#!/usr/bin/env python
"""Health gate: a vector flag that is on without evidence is a red house, not an opinion.

Off is green: the seam is inert and nothing calls it. On is green only when
`backend/vector.gate` opens every door -- flag, evidence shape, production embedder. Today
the last door cannot open because the registry holds only the deterministic test double,
so flipping the flag alone can never pass this gate. That is the point of the phase.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "15_SYSTEM" / "scripts"))
from common import find_root  # noqa: E402
from backend import vector  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    state = vector.gate(root)
    if state["active"]:
        print("OK — vector_search is active under a production embedder and recorded evidence "
              "(gate door: %s)." % state["evidence"])
        return 0
    if state["flag"] is False:
        print("OK — vector_search is off; the embedding seam is inert and nothing calls it.")
        return 0
    print("INVALID vector_search is on but activation is refused:")
    for problem in state["problems"]:
        print("  - %s" % problem)
    return 1


if __name__ == "__main__":
    sys.exit(main())
