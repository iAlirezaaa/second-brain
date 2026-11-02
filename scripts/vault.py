#!/usr/bin/env python
"""Seal and restore the private planes: the encrypted backup, not the note counter.

`scripts/vault_stats.py` counts notes per zone. This tool moves the bytes that must never leave
the machine in the clear -- `.kb` and `.brain-data`, as declared by
`15_SYSTEM/config/system.json -> private_planes`. Charter section 8 asks for both halves of
«بکاپ رمزنگاری‌شده و آزمون منظم Restore»: one authenticated container per seal, and a restore
that somebody actually runs.

Usage:
  python scripts/vault.py --seal [--kdf scrypt|pbkdf2] [--passphrase-file PATH]
  python scripts/vault.py --unseal NAME --into DIR [--overwrite]
  python scripts/vault.py --verify NAME [--passphrase-file PATH]
  python scripts/vault.py --list [--rows N]
  python scripts/vault.py --status
  python scripts/vault.py --bench
  python scripts/vault.py --selftest

NAME is the 14-digit UTC stamp a seal printed, not a path: it is joined to the shelf under one
shape rule, so nothing can hand this tool `../`. The passphrase is asked for twice in a terminal
or read from a file outside the repository -- never from the command line, where `ps` and a CI
log would both keep it.

Every refusal names the rule that refused. A silent skip -- of a symlink, of an oversized file,
of a file that moved while it was read -- would produce a backup that looks complete, and a
partial backup is worse than none because it is trusted.

This command is the mechanism. Whether the feature is *claimed* is a separate door:
`scripts/vault_check.py` refuses to call it active without cross-machine restore evidence, and
the `encrypted_private_backup` flag is false until that evidence exists.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "15_SYSTEM" / "scripts"))
from common import find_root  # noqa: E402
from backend import crypto, vault  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        for line in crypto.run_selftest():
            print(line)
        print("chacha20-poly1305 selftest passed")
        return 0
    if not argv:
        print(__doc__.strip().splitlines()[0])
        print("usage: python scripts/vault.py --seal | --unseal NAME --into DIR | --verify NAME"
              " | --list | --status | --bench | --selftest")
        print("rules: %s" % ", ".join(vault.RULES))
        return 2
    try:
        lines = vault.run(argv, str(find_root(Path(__file__))))
    except (vault.VaultError, crypto.OpenError) as exc:
        # Both carry their rule inside str(exc), so printing it a second time would give one
        # claim two sources. SealError and UnsupportedKDF are deliberately not caught: a cipher
        # that cannot do what it said it does is a bug in this build, not a policy decision.
        print("REFUSED: %s" % exc)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
