#!/usr/bin/env python
"""Health gate: an encrypted-backup claim is a promise that the bytes come back, so it needs a witness.

Off is green: nothing seals, the seam in `backend/vault.py` is inert, and no doc may claim the
vault is protected. On is green only when `backend.vault.gate()` opens every door -- the flag, a
non-empty `private_planes` declaration, and a cross-machine restore witness at
`11_CONTROL/backups/verification.json` whose shape survives the checks. Today the witness cannot
exist because no CI job has sealed on one machine and restored on another, so flipping the flag
alone can never pass this gate. That is the whole design: «بکاپ رمزنگاری‌شده» and «آزمون منظم
Restore» are one claim, and a backup nobody has ever restored is a rumor about a backup.

This gate never touches a key. It reads a flag, a config list and a JSON witness; it does not
derive, does not open a container, and cannot be satisfied by an agent that guessed the numbers.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "15_SYSTEM" / "scripts"))
from common import find_root  # noqa: E402
from backend import vault  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    state = vault.gate(root)
    if state["active"]:
        print("OK — encrypted_private_backup is active: the private planes (%s) are declared and a"
              " restore verified on a different machine than the seal (evidence: %s)."
              % (", ".join(state["private_planes"]), state["evidence"]))
        return 0
    if state["flag"] is False:
        print("OK — encrypted_private_backup is off; sealing is available on request and nothing"
              " claims the private planes are backed up.")
        return 0
    print("INVALID encrypted_private_backup is on but activation is refused:")
    for problem in state["problems"]:
        print("  - %s" % problem)
    return 1


if __name__ == "__main__":
    sys.exit(main())
