#!/usr/bin/env python
"""Install the second brain into a home folder, and move an installed brain onto this engine.

Usage:
  python scripts/install.py [--target ~/brain]              # lay a fresh home
  python scripts/install.py --upgrade ~/brain               # bring that home up to this engine
  python scripts/install.py --upgrade ~/brain --dry-run     # read the plan, write nothing

A brain has one shape wherever it lives: the sixteen zones `system.json` declares, the same
scripts, the same doors, the same eight-plane map. `--target` lays that shape down -- zones first,
then the machine plane (`15_SYSTEM/scripts`, `backend`, schemas, integrations), then the human
documents and the agent doors -- so a fresh home can answer its own gates instead of inheriting the
source repo's map. Nothing needs an app: an installed brain is markdown plus Python standard
library.

The upstream memory stays upstream: the lesson ledger starts empty and the eight planes are
proved by the installed `tests/test_installed_home.py`, not by the source repo's tests.

Why `--upgrade` exists, measured rather than remembered. Before this file grew it, on 2026-11-02,
a home laid by an older engine had no way forward but a manual merge, and the installer said so:

    $ python scripts/install.py --target ~/brain        # a folder that is already a home
    [argparse] error: target ~/brain is not empty — pick a fresh folder

That refusal was correct for its time and useless in the second week. Copying anyway would have
been worse: the home holds notes, lessons and runtime state the repo has never seen, and a flat
overwrite deletes a person's thinking in order to deliver a script.

So an install now ends by hashing what it actually laid, into `15_SYSTEM/generated/install.json`
(`installed_at_utc`, `files` and `engine_bytes`, one sha256 per shipped path, stamped under the
`install-manifest` contract `scripts/schema_stamp.py` owns). `--upgrade` reads that record and asks
one question about every path this engine ships: *are these the bytes we wrote, or the bytes you
wrote?*

  UNCHANGED  the home holds exactly what the record says the installer wrote, and the engine's
             bytes have not moved
  UPDATED    the engine's bytes moved and the home still holds what the installer wrote: rewritten
  ABSENT     the record names a file the home no longer has: restored
  ADDED      this engine ships a path the record never mentions and the home has nothing there
  KEPT       the home's bytes differ from the record, so a person edited them here: never touched,
             and named, because a silent skip is how an upgrade eats someone's notes
  PRESENT    an empty ledger or an empty-folder marker is already there: nothing to lay
  YOURS      the home holds a file at a path this version ships with no record of it, so this act
             cannot tell your file from an outdated one: the file stays exactly where it is, the
             path is deliberately left out of the new record (recording it would teach the next
             act to overwrite it), everything else still moves, and the run exits 1 with the list

Anything the installer never shipped is not in its business. `protected()` names the brain's own
state -- `12_RUNTIME/`, `13_LAB/`, `14_CANDIDATES/` except the shelf contract it lays, the lesson
ledger, `.kb/`, `.brain-data/`, `.obsidian/`, backups -- and a ship plan that lands a real file
there is a bug in this script, so the run refuses and says which path proves it. Nothing is ever
deleted: a file this engine no longer ships stays in the home unread, and the closing line says so.
A file the home *lost* that the record named comes back, because engine scripts are the engine's
business: a home missing `scripts/probe.py` cannot run its own gates, and a gate that was deleted
in 2027 is not a decision this act can honour silently.

The documents a home re-measures for itself (the three `doc_report.py` stamps) get that re-measure
only when none of them is `KEPT` -- this installer will not run a number-filler over a document a
person edited, and will not ship the source repo's measurements into a home it cannot re-measure.
Either way it says which, and names the command that is safe to run by hand.

A `--dry-run` proves itself: the home's tree fingerprint is taken on entry and on exit and must be
identical, so "nothing was written" is a measurement rather than a promise. Every act that writes
re-hashes each file from the disk it landed on, restamps the record only when all of them match,
and appends one line to `15_SYSTEM/logs/install.jsonl` -- what moved, which verdicts it refused,
and the digest of the record that now describes the home.
"""
import argparse
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import memory as memory_mod
from doc_report import DOCS as MEASURED_DOCS
from schema_stamp import stamp_payload
from sync_hosts import HOSTS, render

DOCS = ("README.md", "ROADMAP.md", "HANDOFF.md", "CHANGELOG.md", "AGENTS.md", ".gitignore")
DOC_DIRS = ("00_START_HERE",)
# the executable plane: gates, registry door, backend readers
CODE_DIRS = ("scripts", "rules", "skills")
SYSTEM = ("scripts", "schemas", "memory", "integrations", "migrations", "templates")
STARTER = ("index.md", "_templates")
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "lessons.jsonl")
PROOF = "tests/test_installed_home.py"

MANIFEST_REL = "15_SYSTEM/generated/install.json"
JOURNAL_REL = "15_SYSTEM/logs/install.jsonl"
MANIFEST_CONTRACT = "install-manifest"
# the folders an install mkdir's that hold no bytes to hash, so no manifest row names them
EMPTY_DIRS = ("14_CANDIDATES/loop",)
# what a person writes into. An upgrade lays engine files; it has no business inside this
# brain's own thinking, its quarantine shelf, or the ledgers its own scripts keep.
PROTECTED_DIRS = ("12_RUNTIME/", "13_LAB/", "14_CANDIDATES/", ".kb/", ".brain-data/",
                  ".obsidian/", "15_SYSTEM/backups/", "15_SYSTEM/memory/lessons.jsonl")
# the one file the installer may lay inside a protected folder: the shelf's own contract
PROTECTED_EXCEPTIONS = ("14_CANDIDATES/README.md",)

UNCHANGED = "UNCHANGED"
UPDATED = "UPDATED"
ABSENT = "ABSENT"
ADDED = "ADDED"
KEPT = "KEPT"
YOURS = "YOURS"
PRESENT = "PRESENT"
NOT_IN_REPO = "NOT_IN_REPO"
LAID = "LAID"
# the verdicts that mean "a byte moves"; `YOURS` means "this path does not move, the rest does"
WRITING = (UPDATED, ABSENT, ADDED)


def protected(rel):
    """True when this path belongs to the brain living in the home, not to this engine."""
    if rel in PROTECTED_EXCEPTIONS:
        return False
    return any(rel.startswith(prefix) for prefix in PROTECTED_DIRS)


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


def hash_file(path):
    """The bytes on disk right now, or None when there are no bytes to read."""
    try:
        return sha256_of(Path(path).read_bytes())
    except OSError:
        return None


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def version_text(repo):
    """The engine this act ran under, read beside the repo rather than typed into the record."""
    try:
        return (Path(repo) / "VERSION").read_text(encoding="utf-8").strip() or "(empty VERSION)"
    except OSError:
        return "(no VERSION beside the repo)"


def copy_into(src, dst, label, log):
    if not src.exists():
        log.append("skipped %s (not in the repo)" % label)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True, ignore=IGNORED)
    else:
        shutil.copy2(str(src), str(dst))


def write_doors(repo, target):
    """Reuse the repo's validated bytes; render them here if the repo has none yet."""
    laid = []
    for _key, name, rel, mdc in HOSTS:
        source = repo / rel
        text = source.read_text(encoding="utf-8") if source.is_file() else render(name, mdc)
        door = target / rel
        door.parent.mkdir(parents=True, exist_ok=True)
        door.write_text(text, encoding="utf-8")
        laid.append(rel)
    return laid


def load_config(repo):
    return json.loads((repo / "15_SYSTEM" / "config" / "system.json").read_text(encoding="utf-8"))


def lay_zones(target, cfg, log):
    """The same sixteen zones as the source, empty ones kept by `.gitkeep`."""
    zones = cfg.get("zones") or []
    for zone in zones:
        path = target / zone["dir"]
        path.mkdir(parents=True, exist_ok=True)
        if not any(path.iterdir()):
            (path / ".gitkeep").write_text("", encoding="utf-8")
    log.append("%d zone(s) laid" % len(zones))


def lay_plane_stores(target, cfg):
    """Every tracked store the home's map will claim must be openable in the home."""
    laid = 0
    for spec in (cfg.get("memory_planes") or {}).values():
        for rel in spec.get("tracked_store") or []:
            path = target / rel
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text("", encoding="utf-8")
                    laid += 1
            else:
                path.mkdir(parents=True, exist_ok=True)
                if not any(path.iterdir()):
                    (path / ".gitkeep").write_text("", encoding="utf-8")
                    laid += 1
    return laid


def home_config_bytes(cfg):
    """The map the home can prove: its own stores and readers, one installed proof for all.

    The source document names the source repo's tests. A home has none of them, so copying that
    map would be a claim it cannot keep; the installed proof is the file that ships here.
    """
    installed = copy.deepcopy(cfg)
    installed["home"] = True
    for spec in (installed.get("memory_planes") or {}).values():
        spec["test"] = PROOF
    return (json.dumps(installed, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def init_machine_plane(repo, target, log):
    """A brain with no shelf and no memory cannot learn from its own mistakes.

    The upstream lessons stay upstream: they are evidence about that repo, and a fresh
    brain has not earned them. So the ledger starts empty and legal -- `NO_ENTRY` is the
    honest first answer -- and the first lesson gets written when this brain makes its own.
    """
    copy_into(repo / "14_CANDIDATES" / "README.md", target / "14_CANDIDATES" / "README.md",
              "candidate shelf contract", log)
    for rel in EMPTY_DIRS:
        (target / rel).mkdir(parents=True, exist_ok=True)
    memory_dir = target / "15_SYSTEM" / "memory"
    copy_into(repo / "15_SYSTEM" / "memory" / "README.md", memory_dir / "README.md",
              "memory README", log)
    ledger = memory_dir / "lessons.jsonl"
    if not ledger.exists():
        ledger.write_text("", encoding="utf-8")
    return memory_mod.render(target, memory_mod.read_lessons(target)[0])


# --- the ship plan ------------------------------------------------------------------------------
class Entry(object):
    """One path the installer is responsible for, and where its bytes come from.

    kind `copy`   the repo's own bytes, read from `source`
    kind `render` bytes this file computes (a door with no repo copy, the home's plane map)
    kind `touch`  an empty file, created only when the home has none -- a ledger a home later
                  fills with its own lessons is never truncated
    kind `marker` an empty `.gitkeep`, laid only while the folder is still empty
    """

    def __init__(self, rel, source, kind, label=""):
        self.rel = rel
        self.source = source
        self.kind = kind
        self.label = label

    @property
    def moves_bytes(self):
        """True for the kinds that put shipped content at this path."""
        return self.kind in ("copy", "render")


class Row(object):
    """One entry as this act sees it: the verdict, and the bytes that verdict implies."""

    def __init__(self, entry, verdict, why="", candidate=None):
        self.entry = entry
        self.rel = entry.rel
        self.verdict = verdict
        self.why = why
        self.candidate = candidate


def ignored_name(name):
    """The same three exclusions `IGNORED` gives `copytree`, spelled for a path walk."""
    return name == "__pycache__" or name.endswith(".pyc") or name == "lessons.jsonl"


def flatten(src, rel):
    """[(source path, path the home sees)] for a file or a directory copied into `rel`."""
    src = Path(src)
    if not src.exists():
        return []
    if src.is_file():
        return [] if ignored_name(src.name) else [(src, rel)]
    out = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(src).as_posix().split("/")
        if any(ignored_name(part) for part in parts):
            continue
        out.append((path, "%s/%s" % (rel, "/".join(parts))))
    return out


def ship_plan(repo, cfg):
    """Every path this engine version lays in a home, as one ordered map.

    One list decides both what an install copies and what an upgrade compares, so the upgrade
    cannot end up judging a different set of files from the ones the installer wrote. A path
    named twice keeps the later entry, which is what the sequential copies did before.
    """
    ordered = {}

    def add(rel, source, kind, label=""):
        ordered[rel] = Entry(rel, source, kind, label)

    def add_copy(src, rel, label=""):
        for source, home_rel in flatten(src, rel):
            add(home_rel, source, "copy", label)

    for name in STARTER:
        add_copy(repo / "vault-template" / name, name, "starter %s" % name)
    for name in CODE_DIRS:
        add_copy(repo / name, name, name)
    for name in SYSTEM:
        add_copy(repo / "15_SYSTEM" / name, "15_SYSTEM/%s" % name, "15_SYSTEM/%s" % name)
    add_copy(repo / "15_SYSTEM" / "README.md", "15_SYSTEM/README.md", "15_SYSTEM README")
    add_copy(repo / "02_WIKI" / "reference_maps", "02_WIKI/reference_maps", "eight-plane map")
    for name in DOCS:
        add_copy(repo / name, name, name)
    for name in DOC_DIRS:
        add_copy(repo / name, name, name)
    for harness in (".claude", ".opencode"):
        add_copy(repo / "skills", "%s/skills" % harness, "%s skills" % harness)
    add_copy(repo / PROOF, PROOF, "installed-home proof")
    add_copy(repo / "14_CANDIDATES" / "README.md", "14_CANDIDATES/README.md",
             "candidate shelf contract")
    add_copy(repo / "15_SYSTEM" / "memory" / "README.md", "15_SYSTEM/memory/README.md",
             "memory README")
    for _key, name, rel, mdc in HOSTS:
        source = repo / rel
        if source.is_file():
            add(rel, source, "copy", "%s door" % name)
        else:
            add(rel, render(name, mdc).encode("utf-8"), "render", "%s door" % name)
    add("15_SYSTEM/config/system.json", home_config_bytes(cfg), "render", "the home's plane map")
    add("15_SYSTEM/memory/lessons.jsonl", b"", "touch", "the lesson ledger, empty and legal")
    for zone in (cfg.get("zones") or []):
        if zone.get("dir"):
            add("%s/.gitkeep" % zone["dir"], b"", "marker", "zone %s" % zone["dir"])
    for spec in (cfg.get("memory_planes") or {}).values():
        for rel in spec.get("tracked_store") or []:
            if Path(rel).suffix:
                add(rel, b"", "touch", "plane store %s" % rel)
            else:
                add("%s/.gitkeep" % rel, b"", "marker", "plane store %s" % rel)
    return ordered


def candidate_bytes(entry):
    """What this engine would write at `entry.rel`, or None when the source is gone."""
    if entry.kind != "copy":
        return entry.source
    source = Path(entry.source)
    return source.read_bytes() if source.is_file() else None


# --- the judgement ------------------------------------------------------------------------------
def load_manifest(target):
    """(payload, refusal) -- a home the installer cannot read is a home it must not overwrite."""
    path = Path(target) / MANIFEST_REL
    if not path.is_file():
        return None, ("%s holds no install manifest: this home was laid by an engine that "
                      "recorded nothing, or the record was deleted. An upgrade needs the hashes "
                      "of the bytes the installer wrote to tell them apart from the notes you "
                      "wrote -- without it every file looks edited and every file looks yours. "
                      "Install into a fresh folder and move the human plane across by hand"
                      % MANIFEST_REL)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return None, "%s is not readable JSON (%s) — refuse to judge a home by a record that " \
                     "cannot be parsed" % (MANIFEST_REL, exc)
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        return None, "%s carries no `files` map of hashes, so it records nothing an upgrade can " \
                     "compare — re-run the install into a fresh folder" % MANIFEST_REL
    return payload, None


def judge(plan, manifest, target):
    """One row per shipped path: what the home holds, what the record says we wrote, verdict.

    The record keeps two hashes per path: `files` is the bytes the home ended up holding (for a
    re-measured document, that is this home's own numbers, not the repo's) and `engine_bytes` is
    the bytes this engine's source carried when the act ran. Comparing them instead of each other
    is what lets an upgrade say `UNCHANGED` for a document it re-measured, rather than rewriting
    three files every run and calling that progress.
    """
    recorded = (manifest or {}).get("files") or {}
    engine = (manifest or {}).get("engine_bytes") or {}
    target = Path(target)
    rows = []
    for rel, entry in plan.items():
        observed = hash_file(target / rel)
        was = recorded.get(rel)
        want = candidate_bytes(entry)
        if not entry.moves_bytes:
            if observed is not None:
                rows.append(Row(entry, PRESENT, "already here, and this act does not truncate it"))
            elif entry.kind == "marker" and (target / rel).parent.is_dir() \
                    and any((target / rel).parent.iterdir()):
                folder = (target / rel).parent.relative_to(target).as_posix()
                rows.append(Row(entry, PRESENT, "%s already holds this brain's own files" % folder))
            else:
                rows.append(Row(entry, ADDED if was is None else ABSENT,
                                "laid empty" if was is None else "the record names it, the home "
                                "lost it", want))
            continue
        if want is None:
            rows.append(Row(entry, NOT_IN_REPO, "the source repo ships no such file"))
            continue
        want_hash = sha256_of(want)
        if observed is None:
            rows.append(Row(entry, ADDED if was is None else ABSENT,
                            "new in this engine" if was is None else "missing from the home",
                            want))
        elif was is not None and observed != was:
            rows.append(Row(entry, KEPT, "edited here — left as you wrote it", want))
        elif was is None:
            rows.append(Row(entry, YOURS,
                            "the home holds a file at a path this engine ships and the manifest "
                            "records no hash for it", want))
        elif want_hash != engine.get(rel, was):
            rows.append(Row(entry, UPDATED, "the engine's bytes moved", want))
        else:
            rows.append(Row(entry, UNCHANGED, "", want))
    return rows


def apply_rows(rows, target):
    """(written, failures) -- every write is confirmed by re-hashing the file it landed on."""
    written, failures = [], []
    for row in rows:
        if row.verdict not in WRITING:
            continue
        path = Path(target) / row.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row.candidate)
        written.append(row.rel)
        # a re-measured document keeps its own block-swapped bytes, so its hash is allowed to
        # differ from the repo's; every other path must land byte for byte
        if row.rel in MEASURED_DOCS:
            if not path.is_file():
                failures.append(row.rel)
        elif hash_file(path) != sha256_of(row.candidate):
            failures.append(row.rel)
    return written, failures


def remeasure(target, blocked):
    """Refresh the three stamped documents from this home, or refuse and name what stopped it."""
    if blocked:
        return [], ("not re-measured: %s %s edited here, and this installer will not run a "
                    "number-filler over a document a person wrote, nor ship the source repo's "
                    "measurements into a home it cannot re-measure. Run "
                    "`python scripts/doc_report.py --write` in the home when you want the numbers "
                    "refreshed (it rewrites only the marked block)"
                    % (" and ".join(blocked), "are" if len(blocked) > 1 else "is"))
    result = common.run_utf8(
        [sys.executable, str(Path(target) / "scripts" / "doc_report.py"), "--root", str(target),
         "--write"], cwd=str(target))
    lines = (result.stdout or result.stderr).strip().splitlines()
    if result.returncode:
        return [], "document re-measure failed: %s" % (lines[-1] if lines else "no output")
    return list(MEASURED_DOCS), lines[-1] if lines else ""


def final_state(rows, manifest, target, measured):
    """(files, engine_bytes) -- the two maps the next act judges itself against.

    A `KEPT` row keeps both hashes the record already held. Overwriting them with the home's
    current bytes would make the person's edit invisible to the next run, and the upgrade that
    cannot see an edit is the upgrade that eats it; overwriting the engine hash would claim bytes
    this act never wrote.

    A `YOURS` row is left out of both maps on purpose. Recording an unowned file's bytes as "what
    the installer wrote" would turn the collision into a licence: the next engine change would
    rewrite it as `UPDATED` and the person's file would be gone. Unrecorded, it stays `YOURS` in
    every act until someone decides which file it is.
    """
    recorded = (manifest or {}).get("files") or {}
    engine_record = (manifest or {}).get("engine_bytes") or {}
    files, engine = {}, {}
    for row in rows:
        if row.verdict == KEPT:
            if row.rel in recorded:
                files[row.rel] = recorded[row.rel]
            if row.rel in engine_record:
                engine[row.rel] = engine_record[row.rel]
            continue
        if row.verdict == YOURS:
            continue
        digest = hash_file(Path(target) / row.rel)
        if digest is not None:
            files[row.rel] = digest
        if row.entry.moves_bytes and row.candidate is not None:
            engine[row.rel] = sha256_of(row.candidate)
    for rel in measured:
        digest = hash_file(Path(target) / rel)
        if digest is not None:
            files[rel] = digest
    ordered_files = dict((rel, files[rel]) for rel in sorted(files))
    ordered_engine = dict((rel, engine[rel]) for rel in sorted(engine))
    return ordered_files, ordered_engine


def write_manifest(repo, target, rows, act, manifest, measured=(), notes=()):
    """Lay the record, then prove the bytes on disk are the record this function built."""
    files, engine = final_state(rows, manifest, target, measured)
    payload = {
        "installed_at_utc": now_utc(),
        "files": files,
        "engine_bytes": engine,
        "act": act,
        "engine_version": version_text(repo),
        "kept_edited": [row.rel for row in rows if row.verdict == KEPT],
        "unresolved": [row.rel for row in rows if row.verdict == YOURS],
        "note": ("`files` is the sha256 of the bytes this home held at the end of the act that "
                 "wrote it, `engine_bytes` the sha256 of the source the repo carried then; the two "
                 "differ for the three documents this home re-measures. The record itself, "
                 "15_SYSTEM/logs/install.jsonl (the journal below), anything else under "
                 "15_SYSTEM/generated/ (rebuilt output) and MEMORY.md (rendered from this brain's "
                 "own ledger by scripts/memory.py) are not shipped state and are not hashed here."),
    }
    if notes:
        payload["notes"] = list(notes)
    stamped = stamp_payload(payload, MANIFEST_CONTRACT)
    text = json.dumps(stamped, indent=2, ensure_ascii=False) + "\n"
    path = Path(target) / MANIFEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    # bytes, not write_text: on Windows a text write turns every "\n" into "\r\n", the record
    # then disagrees with the bytes this function hashed, and the same home hashes differently on
    # two machines -- which is exactly the false verdict an upgrade exists to avoid
    path.write_bytes(text.encode("utf-8"))
    if path.read_bytes().decode("utf-8") != text:
        return path, None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return path, None
    if parsed.get("files") != files or parsed.get("engine_bytes") != engine:
        return path, None
    return path, parsed


def append_journal(target, line):
    path = Path(target) / JOURNAL_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
    return path


def counts(rows):
    tally = {}
    for row in rows:
        tally[row.verdict] = tally.get(row.verdict, 0) + 1
    return tally


def print_rows(rows):
    for row in rows:
        if row.verdict in (UNCHANGED, PRESENT):
            continue
        print("%-12s %s%s" % (row.verdict, row.rel,
                              "  (%s)" % row.why if row.why else ""))


def plan_refusals(plan):
    """Ship entries that land on the brain's own state: a bug in this file, not in the home."""
    return [rel for rel, entry in plan.items() if entry.moves_bytes and protected(rel)]


# --- the two acts -----------------------------------------------------------------------------
def do_install(repo, target, log):
    cfg = load_config(repo)
    target.mkdir(parents=True, exist_ok=True)
    for name in STARTER:
        copy_into(repo / "vault-template" / name, target / name, "starter %s" % name, log)
    for name in CODE_DIRS:
        copy_into(repo / name, target / name, name, log)
    for name in SYSTEM:
        copy_into(repo / "15_SYSTEM" / name, target / "15_SYSTEM" / name,
                  "15_SYSTEM/%s" % name, log)
    copy_into(repo / "15_SYSTEM" / "README.md", target / "15_SYSTEM" / "README.md",
              "15_SYSTEM README", log)
    copy_into(repo / "02_WIKI" / "reference_maps",
              target / "02_WIKI" / "reference_maps", "eight-plane map", log)
    for name in DOCS:
        copy_into(repo / name, target / name, name, log)
    for name in DOC_DIRS:
        copy_into(repo / name, target / name, name, log)
    for harness in (".claude", ".opencode"):
        copy_into(repo / "skills", target / harness / "skills", "%s skills" % harness, log)
    copy_into(repo / PROOF, target / PROOF, "installed-home proof", log)
    zones = len(cfg.get("zones") or [])
    lay_zones(target, cfg, log)
    stores = lay_plane_stores(target, cfg)
    doors = write_doors(repo, target)
    index = init_machine_plane(repo, target, log)
    log.append("home config: %d kinds, %d zones, %d planes proved by %s"
               % (len(cfg.get("kinds") or []), zones,
                  len(cfg.get("memory_planes") or {}), PROOF))
    (target / "15_SYSTEM" / "config").mkdir(parents=True, exist_ok=True)
    (target / "15_SYSTEM" / "config" / "system.json").write_bytes(home_config_bytes(cfg))
    # The copied documents carried the source repo's numbers. A brain that reports somebody
    # else's measurements is lying on principle, so the block is re-measured here, from the
    # installed folder, before the first session reads it.
    remeasured, measure_line = remeasure(target, [])
    rows = [Row(entry, LAID, "", candidate_bytes(entry))
            for entry in ship_plan(repo, cfg).values()]
    manifest_path, parsed = write_manifest(repo, target, rows, "install", None, remeasured, log)
    if parsed is None:
        print("REFUSED: %s did not read back as the record this act built; an unhashed home "
              "cannot be upgraded, so the install is reported as incomplete" % MANIFEST_REL)
        return 1
    append_journal(target, {
        "act": "install", "at_utc": now_utc(), "engine_version": version_text(repo),
        "files_hashed": len(parsed["files"]), "manifest_digest": hash_file(manifest_path),
        "note": "a home laid whole"})
    print(f"installed second brain at {target}")
    for line in log:
        print("note: %s" % line)
    print("layout: %d zone(s), %d plane store(s) laid, same shape as the source repo" % (zones, stores))
    print("agent doors written: %s" % ", ".join(doors))
    print("documents re-measured for this home: %s" % measure_line)
    print("empty memory ledger rendered to %s" % index.relative_to(target).as_posix())
    print("record laid: %s (%d file(s) hashed, engine %s) — the bytes an upgrade compares against"
          % (MANIFEST_REL, len(parsed["files"]), version_text(repo)))
    print("act journaled: %s" % JOURNAL_REL)
    print("next (no app required — Python 3.9+ and the scripts are the whole system):")
    print("  cd %s && python scripts/health.py --vault ." % target)
    print("  python -m unittest discover -s tests")
    print("  python 15_SYSTEM/scripts/hades.py doctor")
    print("  python scripts/memory.py --recall \"first session\"")
    print("  open AGENTS.md and follow it; any editor you like is an optional lens "
          "on the same markdown, never a dependency")
    print("  later, from this repo: python scripts/install.py --upgrade %s --dry-run" % target)
    return 0


def do_upgrade(repo, target, dry_run):
    """Move an installed home onto this engine, one judged path at a time, never over a note."""
    before = common.tree_fingerprint(target)
    cfg = load_config(repo)
    manifest, refusal = load_manifest(target)
    print("upgrade %s -> engine %s" % (target, version_text(repo)))
    if refusal:
        print("REFUSED: %s" % refusal)
        return 1
    print("record read: %s (%d file(s) hashed, laid %s under engine %s)"
          % (MANIFEST_REL, len(manifest["files"]), manifest.get("installed_at_utc"),
             manifest.get("engine_version") or "(unrecorded)"))
    plan = ship_plan(repo, cfg)
    for rel in plan_refusals(plan):
        print("REFUSED: the ship plan names %s, which is this brain's own state — the plan is "
              "wrong, not the home, and no byte moves" % rel)
        return 1
    rows = judge(plan, manifest, target)
    tally = counts(rows)
    print("plan: %d shipped path(s) judged — %s"
          % (len(rows), ", ".join("%s %d" % (verdict, tally[verdict])
                                  for verdict in sorted(tally))))
    print_rows(rows)
    yours = [row.rel for row in rows if row.verdict == YOURS]
    for rel in yours:
        print("YOURS      %s  (the home holds this path, the record has no hash for it, and this "
              "act cannot tell your file from an outdated one: left in place, not written, not "
              "recorded)" % rel)
    moving = [row.rel for row in rows if row.verdict in WRITING]
    if dry_run:
        after = common.tree_fingerprint(target)
        print("DRY RUN — %d file(s) would move: %s"
              % (len(moving), ", ".join(sorted(moving)) or "nothing"))
        print("tree %s before and after — nothing was written (a fingerprint that matches is "
              "the proof, not a promise)" % (before if before == after else "CHANGED"))
        if yours:
            print("REFUSED: %d unresolved path(s) above — an upgrade over this home cannot "
                  "finish until each is either moved aside or reinstalled into a fresh folder"
                  % len(yours))
            return 1
        return 0 if before == after else 1
    written, failures = apply_rows(rows, target)
    kept = [row.rel for row in rows if row.verdict == KEPT]
    blocked_docs = [rel for rel in kept if rel in MEASURED_DOCS]
    measured, measure_line = remeasure(target, blocked_docs)
    if failures:
        print("REFUSED: %d file(s) landed and did not read back as written (%s) — the record was "
              "not restamped, so the next run re-judges every path it named"
              % (len(failures), ", ".join(failures)))
        return 1
    manifest_path, parsed = write_manifest(repo, target, rows, "upgrade", manifest, measured)
    if parsed is None:
        print("REFUSED: %s did not read back as the record this act built — the record is not "
              "trusted, so no journal line was written" % MANIFEST_REL)
        return 1
    append_journal(target, {
        "act": "upgrade", "at_utc": now_utc(), "engine_version": version_text(repo),
        "from_engine": manifest.get("engine_version"), "counts": tally, "written": written,
        "kept_edited": kept, "held_documents": blocked_docs, "unresolved": yours,
        "files_hashed": len(parsed["files"]), "manifest_digest": hash_file(manifest_path)})
    print("wrote %d file(s), each re-hashed from disk; kept %d edited file(s) untouched"
          % (len(written), len(kept)))
    print("documents: %s" % measure_line)
    print("record restamped: %s (%d file(s) hashed, engine %s)"
          % (MANIFEST_REL, len(parsed["files"]), version_text(repo)))
    print("act journaled: %s" % JOURNAL_REL)
    print("unchanged %d, already present %d — and nothing the home holds that this engine does "
          "not ship was read, moved or deleted" % (tally.get(UNCHANGED, 0),
                                                   tally.get(PRESENT, 0)))
    if yours:
        print("REFUSED: %d path(s) stayed YOURS and the rest of the home moved. The record did "
              "not learn those paths, so the next act reports them again until you decide which "
              "file each one is" % len(yours))
        return 1
    print("next: cd %s && python scripts/health.py --vault ." % target)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=None)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--upgrade", metavar="HOME", default=None,
                        help="move an installed brain home onto this engine")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="with --upgrade: print the plan, prove nothing was written")
    args = parser.parse_args()
    repo = Path(args.repo)
    if args.upgrade and args.target:
        parser.error("--upgrade and --target are different acts: a fresh home, or an existing one")
    if args.dry_run and not args.upgrade:
        parser.error("--dry-run only means something beside --upgrade; a fresh home is laid or "
                     "is not")
    if args.upgrade:
        home = Path(args.upgrade).expanduser()
        if not home.is_dir():
            parser.error(f"--upgrade {home} is not a folder that exists")
        return do_upgrade(repo, home, args.dry_run)
    target = Path(args.target or "~/brain").expanduser()
    if target.exists() and any(target.iterdir()):
        parser.error(f"target {target} is not empty — pick a fresh folder, or run "
                     f"--upgrade {target} to move this home onto the current engine")
    log = []
    return do_install(repo, target, log)


if __name__ == "__main__":
    sys.exit(main())
