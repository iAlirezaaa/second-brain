"""The private plane, sealed into one authenticated container per run.

Charter section 8 asks for two things at once: «بکاپ رمزنگاری‌شده» and «آزمون منظم Restore».
The first is `crypto.seal_container`; this module is the seam between that primitive and the
real files, and the second belongs to the next phase (a CI job that seals on one machine and
restores on another). Like `vector.py`, this file ships the shape plus a gate that refuses, by
name, every claim it cannot justify -- and the flag `encrypted_private_backup` is false, so
nothing here runs on the owner's vault unless the owner asks it to.

What is private is declared in `15_SYSTEM/config/system.json` -> `private_planes`, not typed
here: `.kb` and `.brain-data` hold the index and the conversation memory, i.e. the bytes that
would say something about a person if they ever left the machine. Recorded known-good bases
are deliberately *not* in that list -- `common.tree_inventory` already skips both planes, so a
base provably carries no private bytes, and sealing the shelf that holds the containers would
make a backup contain itself.

Three laws this module keeps:

* One path rule. Scope entries are judged by `common.safe_rel`, the same predicate the known-good
  base uses, and `crypto.open_container` re-checks every path on the way back in. A manifest
  cannot hand this writer a path it would refuse to seal.
* A refusal always names its rule (SEE RULES below). A silent skip -- of a symlink, of a file too
  big for one frame, of a file that changed size while it was being read -- would produce a backup
  that *looks* complete. A partial backup is worse than no backup, because it is trusted.
* The gate never touches a key. `gate()` reads a flag, a config list and a JSON witness; it does
  not derive, does not open, and cannot be satisfied by an agent that guessed the numbers.
"""
import hashlib
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import common  # noqa: F401  (safe_rel, find_root; path bootstrapped by the package)
from . import crypto

CONFIG = Path("15_SYSTEM") / "config" / "system.json"
EVIDENCE = Path("11_CONTROL") / "backups" / "verification.json"
SHELF = Path("15_SYSTEM") / "backups" / "private"
JOURNAL = "index.jsonl"
KEEP = 5
SUFFIX = ".sbo1"
NAME_RE = re.compile(r"^\d{8}T\d{6}Z$")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
SKIP_DIR_NAMES = {"__pycache__", ".git", ".obsidian", "node_modules"}

# The cipher claim is derived, never typed: if the format version or the magic changes, every
# witness that names the old one stops being evidence on its own.
CIPHER_CLAIM = "%s-%d ChaCha20-Poly1305" % (crypto.MAGIC.decode("ascii"), crypto.VERSION)

RULES = ("plane scope", "empty scope", "symlink in scope", "frame cap", "size moved",
         "container name", "container missing", "shelf in scope", "passphrase source",
         "path set", "refuse to overwrite")

ACTIVATION_KEYS = ("verdict", "cipher", "kdf", "container_sha256", "files", "bytes",
                   "sealed_on", "restored_on", "python_sealed", "python_restored",
                   "ci_run", "approved_by", "approved_at")


class VaultError(Exception):
    """A seal or a restore was refused. `rule` names the law; see RULES."""

    def __init__(self, message, rule):
        if rule not in RULES:
            raise AssertionError("refusal named %r, which is not one of this module's rules" % rule)
        Exception.__init__(self, "%s (rule: %s)" % (message, rule))
        self.rule = rule


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def plane_list(cfg):
    """The declared private planes, validated as a *set of paths*, not trusted as a list.

    Empty is refused rather than honoured: a config that names nothing private turns `--seal`
    into a command that silently backs up nothing, which is the one outcome a backup tool must
    never offer.
    """
    planes = cfg.get("private_planes")
    if not isinstance(planes, list) or not planes:
        raise VaultError("%s has no non-empty `private_planes` list, so this build cannot know"
                         " what counts as private" % CONFIG.as_posix(), "plane scope")
    for plane in planes:
        if common.safe_rel(plane) is None:
            raise VaultError("private plane %r is not a repo-relative path this tool will walk"
                             % plane, "plane scope")
        if plane == SHELF.as_posix() or SHELF.as_posix().startswith(plane + "/"):
            raise VaultError("private plane %r would contain the shelf the containers are written"
                             " to; a backup cannot hold itself" % plane, "shelf in scope")
    return [common.safe_rel(plane) for plane in planes]


def read_config(root):
    path = Path(root) / CONFIG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VaultError("cannot read %s: %s" % (CONFIG.as_posix(), exc), "plane scope")
    if not isinstance(data, dict):
        raise VaultError("%s is not a JSON object" % CONFIG.as_posix(), "plane scope")
    return data


def shelf_dir(root):
    return Path(root) / SHELF


def container_path(root, name):
    if not NAME_RE.match(str(name)):
        raise VaultError("container name %r is not a 14-digit UTC stamp like 20261102T201530Z;"
                         " a name is used to build a path, so it gets one shape and nothing else"
                         % (name,), "container name")
    return shelf_dir(root) / ("priv-%s%s" % (name, SUFFIX))


def collect(root):
    """Every byte inside the declared private planes, as [(repo-relative path, bytes), ...].

    Returns (files, report). The report names what was missing, so `--list` and the seal row can
    say "the index plane was not on this machine" instead of quietly sealing half the vault.
    """
    root = Path(root).resolve()
    planes = plane_list(read_config(root))
    files = []
    missing = []
    for plane in planes:
        base = root / plane
        if not base.is_dir():
            missing.append(plane)
            continue
        for dirpath, dirnames, filenames in os.walk(str(base)):
            dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIR_NAMES)
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                if path.is_symlink():
                    raise VaultError("%s is a symlink: sealing it would store a pointer and a"
                                     " restore could follow it outside the vault"
                                     % path.relative_to(root).as_posix(), "symlink in scope")
                if not path.is_file():
                    continue
                rel = common.safe_rel(path.relative_to(root).as_posix())
                if rel is None:
                    raise VaultError("walked out of the repo at %s" % path, "path set")
                try:
                    declared = path.stat().st_size
                except OSError as exc:
                    raise VaultError("cannot stat %s: %s" % (rel, exc), "size moved")
                if declared > crypto.MAX_FRAME_BYTES:
                    raise VaultError("%s holds %d bytes, over the %d-byte frame cap; this build"
                                     " refuses to write a backup that left a private file"
                                     " out" % (rel, declared, crypto.MAX_FRAME_BYTES), "frame cap")
                payload = path.read_bytes()
                if len(payload) != declared:
                    raise VaultError("%s held %d bytes when read but %d when sized: the file"
                                     " moved while it was being copied, so nothing sealed now can"
                                     " be trusted later" % (rel, len(payload), declared),
                                     "size moved")
                files.append((rel, payload))
    files.sort(key=lambda item: item[0])
    report = {"planes": planes, "missing": missing, "files": len(files),
              "bytes": sum(len(payload) for _, payload in files)}
    if not files:
        why = "absent on this machine" if missing else "present but holding no bytes"
        raise VaultError("the private planes (%s) are %s, and a backup of nothing is not a"
                         " backup" % (", ".join(missing or planes), why), "empty scope")
    return files, report


def _read_rows(root):
    path = shelf_dir(root) / JOURNAL
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            rows.append({"_unreadable": line})
            continue
        rows.append(row if isinstance(row, dict) else {"_unreadable": line})
    return rows


def _append_row(root, row):
    shelf_dir(root).mkdir(parents=True, exist_ok=True)
    path = shelf_dir(root) / JOURNAL
    with open(str(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _prune(root):
    """Rotate the bytes, never the rows: the journal keeps every seal it ever recorded."""
    shelf = shelf_dir(root)
    containers = sorted(p for p in shelf.glob("priv-*" + SUFFIX) if p.is_file())
    removed = []
    while len(containers) > KEEP:
        oldest = containers.pop(0)
        try:
            oldest.unlink()
            removed.append(oldest.name)
        except OSError:
            break
    return removed


def seal(root, passphrase, kdf=crypto.KDF_SCRYPT):
    """Seal the private planes into one new container. Returns the row that describes it."""
    if isinstance(passphrase, bytes) and not passphrase:
        raise VaultError("refusing to seal with an empty passphrase", "passphrase source")
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    files, report = collect(root)
    blob = crypto.seal_container(files, passphrase, kdf)
    name = stamp()
    path = container_path(root, name)
    shelf_dir(root).mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise VaultError("%s already exists; two seals in the same second would overwrite one"
                         " another" % path.name, "refuse to overwrite")
    with open(str(path), "xb") as handle:
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())
    row = {"kind": "seal", "name": name, "container": "%s/%s" % (SHELF.as_posix(), path.name),
           "cipher": CIPHER_CLAIM, "kdf": kdf, "container_sha256": crypto.container_digest(blob),
           "files": len(files), "plain_bytes": report["bytes"], "bytes": len(blob),
           "planes": report["planes"], "missing_planes": report["missing"],
           "created": now(), "python": platform.python_version(),
           "platform": platform.system().lower(), "host": platform.node()}
    _append_row(root, row)
    row["pruned"] = _prune(root)
    return row


def _require_container(root, name):
    path = container_path(root, name)
    if not path.is_file():
        shelf = shelf_dir(root)
        on_shelf = sorted(p.name[len("priv-"):-len(SUFFIX)]
                          for p in shelf.glob("priv-*" + SUFFIX)) if shelf.is_dir() else []
        raise VaultError("no container named %r at %s; the shelf holds %s"
                         % (name, SHELF.as_posix(), ", ".join(on_shelf) or "nothing"),
                         "container missing")
    return path


def inspect(root, name):
    """Read the structure without a passphrase: how many frames, how many bytes, which KDF.

    Deliberately not a list of paths -- the manifest is itself inside an encrypted frame, so the
    names of a person's notes stay secret from anyone who steals the container but not the key.
    """
    path = _require_container(root, name)
    blob = path.read_bytes()
    parsed = crypto.parse_container(blob)
    return {"name": name, "container": "%s/%s" % (SHELF.as_posix(), path.name),
            "cipher": CIPHER_CLAIM, "version": parsed["version"], "kdf": parsed["kdf"],
            "frames": len(parsed["frames"]), "sealed_bytes": len(blob),
            "container_sha256": crypto.container_digest(blob),
            "header_sha256": hashlib.sha256(json.dumps(parsed["header"], sort_keys=True)
                                            .encode("utf-8")).hexdigest()}


def verify(root, name, passphrase):
    """Open a container and check every byte against what the shelf says it held. Writes nothing."""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    path = _require_container(root, name)
    blob = path.read_bytes()
    digest = crypto.container_digest(blob)
    files = crypto.open_container(blob, passphrase)
    opened = sorted([(rel, len(payload)) for rel, payload in files])
    expected = None
    for row in _read_rows(root):
        if row.get("name") == name and row.get("kind") == "seal":
            expected = row
    if expected and expected.get("container_sha256") != digest:
        raise VaultError("%s reads as %s but the journal recorded %s: this is not the container"
                         " that was sealed" % (name, digest, expected.get("container_sha256")),
                         "container missing")
    return {"name": name, "container_sha256": digest, "files": len(files),
            "plain_bytes": sum(size for _, size in opened), "entries": opened}


def restore(root, name, into, passphrase, overwrite=False):
    """Open a container and lay its bytes under `into`. Nothing is written until all of it authenticated.

    `crypto.open_container` returns only after every frame's tag has verified, so a wrong
    passphrase, a spliced frame or a truncated container leaves the destination untouched. After
    that the targets are checked for collisions before the first write, and a write that fails
    half-way is unwound -- a restore that leaves a directory of mixed generations is the failure
    mode an owner cannot see.
    """
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    path = _require_container(root, name)
    blob = path.read_bytes()
    digest = crypto.container_digest(blob)
    files = crypto.open_container(blob, passphrase)
    into = Path(into)
    targets = []
    for rel, payload in files:
        safe = common.safe_rel(rel)
        if safe is None:
            raise VaultError("container %s authenticated but carries the path %r, which this"
                             " build never seals" % (name, rel), "path set")
        targets.append((into / safe, payload, safe))
    if not overwrite:
        taken = [safe for target, _, safe in targets if target.exists()]
        if taken:
            raise VaultError("refusing to overwrite %d existing file(s) under %s: %s"
                             % (len(taken), into, ", ".join(sorted(taken)[:5])),
                             "refuse to overwrite")
    into.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for target, payload, safe in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(str(target), "wb") as handle:
                handle.write(payload)
            written.append(target)
    except OSError as exc:
        for target in written:
            try:
                target.unlink()
            except OSError:
                pass
        raise VaultError("writing %s failed (%s); the %d file(s) already placed were removed, so"
                         " the destination holds nothing from this attempt"
                         % (safe, exc, len(written)), "refuse to overwrite")
    _append_row(root, {"kind": "restore", "name": name, "container_sha256": digest,
                       "files": len(files), "plain_bytes": sum(len(p) for _, p, _ in targets),
                       "into": str(into), "created": now(),
                       "python": platform.python_version(), "platform": platform.system().lower(),
                       "host": platform.node()})
    return {"name": name, "files": len(files), "into": str(into),
            "plain_bytes": sum(len(payload) for _, payload, _ in targets),
            "container_sha256": digest}


def rows(root, limit=0):
    data = _read_rows(root)
    return data[-limit:] if limit else data


def status(root):
    shelf = shelf_dir(root)
    containers = sorted(p.name for p in shelf.glob("priv-*" + SUFFIX)) if shelf.is_dir() else []
    state = gate(root)
    return {"shelf": SHELF.as_posix(), "containers": containers, "on_disk": len(containers),
            "keep": KEEP, "journal_rows": len(_read_rows(root)),
            "cipher": CIPHER_CLAIM, "active": state["active"], "flag": state["flag"],
            "private_planes": state["private_planes"], "problems": state["problems"]}


def bench(byte_count=1048576, kdf=crypto.KDF_PBKDF2):
    """Measure a realistic seal. Default KDF is pbkdf2 because scrypt at 2**15 would dominate
    the number and hide the throughput the owner actually pays for."""
    payload = bytes(byte_count)
    started = time.monotonic()
    blob = crypto.seal_container([("probe.bin", payload)], b"bench", kdf)
    sealed_in = time.monotonic() - started
    started = time.monotonic()
    crypto.open_container(blob, b"bench")
    opened_in = time.monotonic() - started
    meg = byte_count / 1048576.0
    return {"bytes": byte_count, "kdf": kdf, "container_bytes": len(blob),
            "seal_seconds": round(sealed_in, 4), "open_seconds": round(opened_in, 4),
            "seal_mb_per_second": round(meg / sealed_in, 3) if sealed_in else 0.0,
            "open_mb_per_second": round(meg / opened_in, 3) if opened_in else 0.0}


def passphrase_from_file(path, root):
    """Read a key from a file -- but never one the repository can see.

    A passphrase inside the repo is a passphrase in Git: it would ride the very clone this
    feature exists to make safe, and it would be sealed inside its own container. So the path is
    refused if it resolves under the repo root, and the value is never taken from argv, where
    `ps` and a CI log would both keep it.
    """
    candidate = Path(path).resolve()
    root = Path(root).resolve()
    if not candidate.is_file():
        raise VaultError("--passphrase-file %s is not a file" % path, "passphrase source")
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate.read_bytes().rstrip(b"\r\n")
    raise VaultError("--passphrase-file %s resolves inside the repository (%s): a key stored with"
                     " the data it protects protects nothing, and it would be pushed"
                     % (path, root), "passphrase source")


def _read_flags(root):
    data = read_config(root)
    flags = data.get("feature_flags") if isinstance(data, dict) else None
    if not isinstance(flags, dict):
        raise VaultError("%s has no feature_flags object" % CONFIG.as_posix(), "plane scope")
    return flags


def _evidence_problems(data):
    """Shape, not vibes. A witness that cannot answer these questions is not evidence."""
    if not isinstance(data, dict):
        return ["evidence is not a JSON object"]
    missing = [key for key in ACTIVATION_KEYS if key not in data]
    if missing:
        return ["evidence is missing %s" % ", ".join(missing)]
    problems = []
    if data.get("verdict") != "roundtrip_verified":
        problems.append("verdict is %r, not 'roundtrip_verified'" % (data.get("verdict"),))
    if data.get("cipher") != CIPHER_CLAIM:
        problems.append("evidence names cipher %r; this build writes %r, so the container it"
                        " describes was made by something else" % (data.get("cipher"), CIPHER_CLAIM))
    if data.get("kdf") not in crypto.KDF_PARAMS:
        problems.append("kdf %r is not one this build honours (%s)"
                        % (data.get("kdf"), ", ".join(sorted(crypto.KDF_PARAMS))))
    if not HEX64_RE.match(str(data.get("container_sha256") or "")):
        problems.append("container_sha256 must be the 64-hex digest of the sealed bytes"
                        " -- of the ciphertext, never of the plaintext")
    for key in ("files", "bytes"):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            problems.append("%s must be a positive int of what the round trip carried" % key)
    sealed_on = str(data.get("sealed_on") or "").strip().casefold()
    restored_on = str(data.get("restored_on") or "").strip().casefold()
    if not sealed_on or not restored_on:
        problems.append("sealed_on and restored_on must both name a machine")
    elif sealed_on == restored_on:
        problems.append("sealed_on == restored_on (%r): a round trip on one machine proves the"
                        " codec, not that the bytes survive a machine that never saw them"
                        % sealed_on)
    for key in ("python_sealed", "python_restored"):
        if not re.match(r"^\d+\.\d+", str(data.get(key) or "").strip()):
            problems.append("%s must record the interpreter version that ran that side" % key)
    run = str(data.get("ci_run") or "").strip()
    if not (re.match(r"^\d{6,}$", run) or run.startswith("https://")):
        problems.append("ci_run must be a workflow run id or an https URL, so a reader can open"
                        " the job that ran the restore")
    if not str(data.get("approved_by") or "").strip():
        problems.append("approved_by is empty -- an agent cannot approve this")
    approved_at = str(data.get("approved_at") or "")
    try:
        datetime.strptime(approved_at, "%Y-%m-%d")
    except ValueError:
        problems.append("approved_at must be an ISO date")
    return problems


def gate(root):
    """Every door, named. Active only when the flag is true, the planes are declared and the
    cross-machine witness survives its shape checks.

    No key derivation and no container read happen here: a health gate that opens a vault would
    need the passphrase, and a gate that needs a secret is a gate that gets skipped.
    """
    root = Path(root)
    try:
        flags = _read_flags(root)
    except VaultError as exc:
        return {"active": False, "flag": None, "problems": [str(exc)], "private_planes": [],
                "evidence": EVIDENCE.as_posix(), "cipher": CIPHER_CLAIM,
                "shelf": SHELF.as_posix()}
    flag = bool(flags.get("encrypted_private_backup"))
    problems = []
    if not flag:
        problems.append("feature_flags.encrypted_private_backup is false")
    try:
        planes = plane_list(read_config(root))
    except VaultError as exc:
        planes = []
        problems.append(str(exc))
    evidence_path = root / EVIDENCE
    if not evidence_path.is_file():
        problems.append("no cross-machine restore evidence at %s" % EVIDENCE.as_posix())
    else:
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append("evidence is unreadable: %s" % exc)
        else:
            problems.extend(_evidence_problems(evidence))
    return {"active": not problems, "flag": flag, "problems": problems,
            "evidence": EVIDENCE.as_posix(), "cipher": CIPHER_CLAIM,
            "private_planes": planes, "shelf": SHELF.as_posix()}


def run(argv, root):
    """The body behind `scripts/vault.py`: same argv words, no printing."""
    import argparse
    parser = argparse.ArgumentParser(prog="vault.py")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--seal", action="store_true")
    action.add_argument("--unseal", metavar="NAME")
    action.add_argument("--verify", metavar="NAME")
    action.add_argument("--list", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--bench", action="store_true")
    parser.add_argument("--into", default=None)
    parser.add_argument("--passphrase-file", default=None)
    parser.add_argument("--kdf", default=crypto.KDF_SCRYPT, choices=sorted(crypto.KDF_PARAMS))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--rows", type=int, default=10)
    parser.add_argument("--root", default=None,
                        help="vault root to act on (default: the caller's repo root)")
    args = parser.parse_args(argv)
    if args.root:
        root = args.root

    if args.seal:
        row = seal(root, _passphrase(args, root), args.kdf)
        return ["sealed %s: %d files, %d plaintext bytes -> %d container bytes"
                % (row["name"], row["files"], row["plain_bytes"], row["bytes"]),
                "container: %s" % row["container"],
                "sha256 (of the ciphertext): %s" % row["container_sha256"],
                "cipher: %s | kdf: %s" % (row["cipher"], row["kdf"]),
                "planes: %s%s" % (", ".join(row["planes"]),
                                  " (absent here: %s)" % ", ".join(row["missing_planes"])
                                  if row["missing_planes"] else ""),
                "pruned: %s" % (", ".join(row["pruned"]) if row["pruned"] else "nothing")]
    if args.verify:
        report = verify(root, args.verify, _passphrase(args, root))
        return ["verified %s: %d files, %d plaintext bytes, every frame authenticated"
                % (report["name"], report["files"], report["plain_bytes"]),
                "container sha256: %s" % report["container_sha256"]]
    if args.unseal:
        if not args.into:
            raise VaultError("--unseal needs --into DIR: restoring into the vault itself would"
                             " overwrite the live private plane with an old generation",
                             "refuse to overwrite")
        report = restore(root, args.unseal, args.into, _passphrase(args, root), args.overwrite)
        return ["restored %s: %d files, %d bytes -> %s"
                % (report["name"], report["files"], report["plain_bytes"], report["into"])]
    if args.list:
        state = status(root)
        lines = ["shelf %s: %d container(s) kept of every seal (journal rows: %d), keep=%d"
                 % (state["shelf"], state["on_disk"], state["journal_rows"], state["keep"])]
        if not state["containers"]:
            lines.append("nothing sealed yet on this machine")
        for filename in state["containers"]:
            name = filename[len("priv-"):-len(SUFFIX)]
            try:
                info = inspect(root, name)
            except crypto.OpenError as exc:
                # A shelf is read most often when something has already gone wrong. Naming the
                # damaged container and carrying on is the only honest way to answer "what is
                # on the shelf?"; a traceback would hide the containers that are still good.
                lines.append("  %s  UNREADABLE: %s" % (name, exc))
                continue
            lines.append("  %s  %d frames  %d bytes  kdf=%s  sha256=%s"
                         % (info["name"], info["frames"], info["sealed_bytes"], info["kdf"],
                            info["container_sha256"][:16]))
        for row in rows(root, args.rows):
            if row.get("_unreadable"):
                lines.append("  journal row unparseable: %r" % row["_unreadable"][:60])
                continue
            lines.append("  %s %s %s: %d files / %d bytes"
                         % (row.get("kind"), row.get("name"), row.get("created"),
                            row.get("files", 0), row.get("plain_bytes", 0)))
        return lines
    if args.status:
        state = status(root)
        lines = ["encrypted_private_backup: %s" % ("ACTIVE" if state["active"] else "inert"),
                 "cipher: %s" % state["cipher"],
                 "private planes: %s" % (", ".join(state["private_planes"]) or "(none declared)"),
                 "shelf: %s (%d container(s))" % (state["shelf"], state["on_disk"])]
        for problem in state["problems"]:
            lines.append("  door still shut: %s" % problem)
        return lines
    measured = bench()
    return ["bench: %d bytes sealed in %.4fs (%.3f MB/s), opened in %.4fs (%.3f MB/s),"
            " container %d bytes, kdf=%s"
            % (measured["bytes"], measured["seal_seconds"], measured["seal_mb_per_second"],
               measured["open_seconds"], measured["open_mb_per_second"],
               measured["container_bytes"], measured["kdf"])]


def _passphrase(args, root):
    if args.passphrase_file:
        return passphrase_from_file(args.passphrase_file, root)
    # stdout too: on Windows the NUL device answers stdin.isatty() with True, so a redirected
    # run (CI, an agent) would block in getpass forever instead of refusing.
    if not sys.stdin or not sys.stdin.isatty() or not sys.stdout or not sys.stdout.isatty():
        raise VaultError("there is no terminal to ask in and no --passphrase-file was given;"
                         " a passphrase belongs in a file outside the repository or in the"
                         " hands of the person typing it, never in a command line",
                         "passphrase source")
    import getpass
    first = getpass.getpass("passphrase for the private vault: ")
    if first != getpass.getpass("repeat it: "):
        raise VaultError("the two passphrases did not match, so nothing was sealed or opened",
                         "passphrase source")
    return first
