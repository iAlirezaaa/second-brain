#!/usr/bin/env python
"""Status and self-test for the embedding seam -- which is off, and has nothing to download.

Usage:
  python scripts/vector.py status [--root path]
  python scripts/vector.py probe

`status` answers one question: is vector search active, off, or refused? "Refused" means the
flag was flipped but the evidence, the embedder registry, or both do not justify it. `probe`
runs the deterministic test double over a fixed corpus: same output across processes, no
socket, no model. It measures the seam, not retrieval quality.
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

DOCS = [
    ("ranking.md", "bm25 ranks documents by term frequency and inverse document frequency"),
    ("schedule.md", "a schedule record governs when the improvement loop is due"),
    ("lesson.md", "a lesson needs an exact quote from an imported source"),
    ("sync.md", "two devices that disagree keep both versions and name the conflict"),
    ("persian.md", "یادگیری و حافظه باید با منبع بازیابی شوند"),
]
QUERIES = ["bm25 ranking", "schedule due", "یادگیری حافظه"]


def status(root):
    state = vector.gate(root)
    if state["active"]:
        print("ACTIVE — vector_search is on: flag, evidence and a production embedder all hold.")
        return 0
    if state["flag"] is False:
        print("OFF — vector_search is false in %s; the seam is inert (registered: %s)."
              % (vector.CONFIG.as_posix(), ", ".join(state["registered"])))
        return 0
    print("REFUSED — vector_search asks to be on, and these doors are shut:")
    for problem in state["problems"]:
        print("  - %s" % problem)
    return 1


def probe():
    first, second = vector.HashingEmbedder(), vector.HashingEmbedder()
    sample = "bm25 ranking"
    repeatable = first.embed(sample) == second.embed(sample) == first.embed(sample)
    print("embedder=%s dims=%d production=%s" % (first.name, first.dims,
                                                  bool(first.production)))
    print("repeat: %s across two instances and three calls"
          % ("identical" if repeatable else "DIFFERENT"))
    print("network: hashlib only; no socket is opened")
    for query in QUERIES:
        hits = vector.rank(DOCS, query, first, limit=2)
        print("query %r -> %s" % (query, ", ".join("%s %.3f" % (name, score)
                                                   for score, name in hits) or "no hits"))
    return 0 if repeatable else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "probe"])
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    if args.command == "probe":
        return probe()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    return status(root)


if __name__ == "__main__":
    sys.exit(main())
