#!/usr/bin/env python
"""Every generated JSON file says which contract wrote it, and a gate reads that sentence.

Why this exists (phase 44, borrowed from graphify): `graph.json` carries `graph.schema_version`
inside the file itself, "so integrations can detect incompatible format changes". A JSON file
with no version in it can only be *guessed* at: the reader opens it, finds the keys it remembers,
and calls the rest noise. When the writer's shape moves, the reader does not fail -- it mis-parses
quietly, and prints a green result over a file it cannot actually see. The repo's own law calls
that a silent gate, so the stamp goes in at write time and this file is the gate that refuses a
missing or stale one.

One place owns the contract: the table below says which writer produces which file, which version
it stamps, and which fields prove a file really is what the table claims. A writer in another
folder reads its own version from `15_SYSTEM/config/system.json` (the plane map's number) or calls
`stamp_payload()` here; neither copy is a second truth.

The starting state, measured rather than remembered. Before this change, on 2026-11-02, in this
folder, this command printed the count of JSON files that declared their own contract:

    $ python - <<'EOF'
    > import json, pathlib
    > files = sorted(p for p in pathlib.Path(".").rglob("*.json")
    >                if "__pycache__" not in p.parts and ".git" not in p.parts)
    > stamped = [p for p in files
    >            if isinstance(json.loads(p.read_text(encoding="utf-8")), dict)
    >            and "schema_version" in json.loads(p.read_text(encoding="utf-8"))]
    > print(len(stamped), "of", len(files))
    > EOF
    2 of 44

and the same measure over the files a clone actually carries (`git ls-files "*.json"`) was:

    $ python -c "import json,subprocess,pathlib;rels=subprocess.run(['git','ls-files','*.json'],
    capture_output=True,text=True).stdout.split();print(len([r for r in rels if 'schema_version'
    in json.loads(pathlib.Path(r).read_text(encoding='utf-8'))]),'of',len(rels))"
    1 of 34

Two of the stamped ones (`15_SYSTEM/config/system.json`, `15_SYSTEM/generated/catalog.json`) were
written by `hades.py`; `catalog.json` is gitignored, so a fresh clone carried exactly one stamped
JSON file out of thirty-four. `scripts/kb.py`'s `SCHEMA = "2"` is *not* this kind of stamp: it is
the version of a sqlite index rebuilt from scratch, and no JSON file reads it.

The debt was then paid by this file's own command, which refuses to paint a number over a shape it
cannot check:

    $ python scripts/schema_stamp.py --stamp --write
    STAMPED 32 file(s); 12 named above needed nothing (already stamped, hand-authored, or
    disposable)

and the two measures above then printed `34 of 44` and `24 of 34`. The ten tracked files that still
carry no `schema_version` are exactly the hand-authored ones `--check` prints as AUTHORED -- four
under `rules/`, two under `tests/fixtures/`, the two integration examples, `manifest.schema.json`
and a workflow's `steps.json` -- each named with its reason, none skipped silently;
`15_SYSTEM/config/system.json` carries the number because it *is* the source of it, and the gate
still refuses to grade it against itself. Raw counts like these drift while other writers run, so
the number worth quoting is the gate's own line, which over the shipped tree printed:

    OK - 48 JSON file(s) opened and judged by name: 37 stamped, 11 hand-authored,
    0 behind the git boundary, 0 missing, 0 stale, 0 unreadable, 0 claimed by no contract

Usage:
  python scripts/schema_stamp.py --check             # the gate: one line per JSON file, by name
  python scripts/schema_stamp.py --list              # the same enumeration, no verdict
  python scripts/schema_stamp.py --writers           # the table: who stamps which version
  python scripts/schema_stamp.py --stamp             # dry run of the one debt-payment command
  python scripts/schema_stamp.py --stamp --write     # enter a missing stamp, byte-preservingly

Exit 0 = every JSON file this folder holds was opened and judged by name; 1 = a file carries no
stamp, carries a stamp its contract disagrees with, cannot be parsed, or matches no contract at
all. `--stamp` refuses three things: a file whose fields do not match its contract (it is not that
kind of file), a file whose stamp already disagrees with its contract (painting the number over a
stale file is the fabrication this gate exists to catch -- regenerate it with its writer), and a
file whose bytes are not the one-key-per-line shape its writer produces (re-serialising shipped
data would rewrite far more than the stamp). `--write` on its own is refused before it can touch
anything.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINGERPRINT_SKIP_DIRS, clone_readable, find_root  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

STAMP = "schema_version"
SYSTEM_JSON = "15_SYSTEM/config/system.json"

# what a contract says about the files it owns
GENERATED = "generated"     # a script writes them: the writer declares the version
LEDGER = "ledger"           # a person writes them, a script reads and refuses them
CONTRACT = "contract"       # hand-written law or fixture: no version to check

# the version a hades writer stamps is the number the plane map itself declares; writing a
# literal "3.0.0" here would put the same fact in two places and let them drift
CONFIG_VERSION = "config"

STAMPED = "stamped"
MISSING = "missing"
STALE = "stale"
NOT_GENERATED = "not-a-generated-file"
OUT_OF_BOUNDARY = "behind-the-git-boundary"
UNREADABLE = "unreadable"
UNCLASSIFIED = "unclassified"

REFUSAL_STATES = (MISSING, STALE, UNREADABLE, UNCLASSIFIED)


def _dict_with(*keys):
    """Content matcher: a dict carrying every key named (never a filename)."""
    def matcher(rel, data):
        return isinstance(data, dict) and all(key in data for key in keys)
    return matcher


def _path_under(*prefixes):
    """Path matcher for the folders a person writes into: law, fixtures, examples."""
    def matcher(rel, data):
        return any(rel == prefix or rel.startswith(prefix) for prefix in prefixes)
    return matcher


class Contract(object):
    """One family of JSON files: who writes it, which version they stamp, what proves it."""

    def __init__(self, name, kind, writer, version, matcher, fields=(), why=""):
        self.name = name
        self.kind = kind
        self.writer = writer
        self.version = version
        self.matcher = matcher
        self.fields = tuple(fields)
        self.why = why

    def claims(self, rel, data):
        return bool(self.matcher(rel, data))

    def holds(self, data):
        """True when the payload carries the fields that decide how a reader parses it."""
        return isinstance(data, dict) and all(field in data for field in self.fields)


CONTRACTS = (
    # ---- written by hades.py: every JSON the registry plane holds goes through dump_json ----
    Contract("registry-plan", GENERATED, "15_SYSTEM/scripts/hades.py", CONFIG_VERSION,
             _dict_with("plan_id", "record"), fields=("plan_id", "record"),
             why="an approved structural change, bound to the bytes it was written against"),
    Contract("registry-catalog", GENERATED, "15_SYSTEM/scripts/hades.py", CONFIG_VERSION,
             _dict_with("generated_at_utc", "records"),
             fields=("generated_at_utc", "records", STAMP),
             why="the rebuilt index `hades.py index` lays down; gitignored, so a clone has none"),
    Contract("registry-record", GENERATED, "15_SYSTEM/scripts/hades.py", CONFIG_VERSION,
             _dict_with("id", "kind"),
             fields=("id", "kind", "name", "status", "classification", "created_at"),
             why="a registry manifest: the definition `doctor`, `index`, `show` and the harness "
                 "doors read before acting"),
    # ---- written by scripts/loop.py once per improvement cycle ----
    Contract("loop-history", GENERATED, "scripts/loop.py", "1", _dict_with("runs"),
             fields=("runs",),
             why="the ratchet's own past runs; the shape of `runs` decides whether a regression "
                 "can be compared at all"),
    # ---- written by scripts/install.py into the home it installs, never into this repo ----
    Contract("install-manifest", GENERATED, "scripts/install.py", "1",
             _dict_with("installed_at_utc", "files"), fields=("installed_at_utc", "files"),
             why="one sha256 per path the installer laid, measured from the home. It is what "
                 "tells a note a person wrote from a script that fell behind, so `--upgrade` can "
                 "rewrite the second and refuse the first; `files` being a map of digests is the "
                 "whole contract, and a reader that guesses at its shape guesses at a home"),
    # ---- no script writes this one today; scripts/issues.py reads it and refuses what it " ----
    # ---- cannot judge, so the version is entered when the shape changes (measured with:    ----
    # ---- grep -rn '"issues.json"' --include=*.py . -> only reads)                          ----
    Contract("issue-ledger", LEDGER, "scripts/issues.py", "1", _dict_with("repo", "issues"),
             fields=("repo", "issues"),
             why="the checked-in issue ledger `issues.py --check` judges row by row; a person "
                 "updates it, so this gate is what notices a missing stamp"),
    # ---- hand-authored: judged by their own laws, not by a stamp they cannot carry ----
    Contract("plane-map", CONTRACT, "a person, through hades.py's readers", CONFIG_VERSION,
             _path_under(SYSTEM_JSON),
             why="it DECLARES the version every registry writer stamps; checking it against "
                 "itself would be a loop, so it is named here instead"),
    Contract("zone-law", CONTRACT, "a person (read by scripts/zone_check.py)", None,
             _path_under("rules/"),
             why="hand-written law; `rules/*.schema.json` and `rules/zones.json` are the "
                 "contracts other gates read, not generated output"),
    Contract("manifest-schema", CONTRACT, "a person (read by hades.py)", None,
             _path_under("15_SYSTEM/schemas/"),
             why="the record contract `doctor` enforces; it is the thing a stamp points at"),
    Contract("test-fixture", CONTRACT, "a person (read by tests/)", None,
             _path_under("tests/fixtures/"),
             why="expected data a person curated: `retrieval-independent-eval.json` says so in "
                 "its own `provenance` field (\"Curated by hand on 2026-10-29\"); a generated "
                 "answer key would make the tests reading it prove nothing"),
    Contract("host-example", CONTRACT, "a person (copied by a reader)", None,
             _path_under("15_SYSTEM/integrations/"),
             why="an example config for another app's door, never read by this repo's gates"),
    Contract("workflow-body", CONTRACT, "a person (run by backend/orchestrator.py)", None,
             _dict_with("steps"),
             why="the executable `steps.json` a person writes; the registry record beside it "
                 "carries the stamp that governs the pair"),
)

CONTRACT_BY_NAME = dict((c.name, c) for c in CONTRACTS)


# --- the audit ---------------------------------------------------------------------------------
def load_payload(path):
    """(data, error) -- a file that cannot be parsed is a finding, never a silent skip."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, "cannot be read: %s" % exc
    try:
        return json.loads(text), None
    except ValueError as exc:
        return None, "is not JSON: %s" % exc


def json_files(root):
    """Every JSON a reader of this folder can open, minus the noise no reader can judge."""
    root = Path(root)
    out = []
    for path in sorted(root.rglob("*.json")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if set(rel.split("/")[:-1]) & set(FINGERPRINT_SKIP_DIRS):
            continue
        out.append((rel, path))
    return out


def contract_for(rel, data):
    for contract in CONTRACTS:
        if contract.claims(rel, data):
            return contract
    return None


def config_version(root, cache=None):
    """The number the plane map declares -- read from the disk it is quoted from."""
    if cache is not None and CONFIG_VERSION in cache:
        return cache[CONFIG_VERSION]
    data, error = load_payload(Path(root) / SYSTEM_JSON)
    version = data.get(STAMP) if isinstance(data, dict) else None
    if error or not version:
        version = None
    if cache is not None:
        cache[CONFIG_VERSION] = version
    return version


def expected_version(contract, root, cache=None):
    return (config_version(root, cache) if contract.version == CONFIG_VERSION
            else contract.version)


def judge(rel, path, root, cache=None):
    """One file -> one row saying what this gate saw, in the file's own name."""
    row = {"path": rel, "contract": None, "state": None, "found": None, "expected": None,
           "writer": None, "why": "", "kind": None}
    data, error = load_payload(path)
    if error:
        row.update(state=UNREADABLE, why=error, writer="(any)")
        return row
    contract = contract_for(rel, data)
    if contract is None:
        if clone_readable(rel):
            row.update(state=UNCLASSIFIED,
                       why="no contract in this table claims it, and a clone carries it: either "
                           "a new writer is stamping nothing, or a hand-authored file needs its "
                           "reason declared here by name")
        else:
            row.update(state=OUT_OF_BOUNDARY,
                       why="disposable local state behind the documented git boundary "
                           "(common.clone_readable): a fresh clone holds nothing at this path, "
                           "and no contract in this table owns it yet -- named, not skipped")
        return row
    row.update(contract=contract.name, writer=contract.writer, kind=contract.kind)
    if contract.kind == CONTRACT:
        row.update(state=NOT_GENERATED, why=contract.why, found=data.get(STAMP))
        return row
    if not contract.holds(data):
        row.update(state=UNCLASSIFIED,
                   why="%s does not hold the fields the %s contract names (%s), so it is not "
                       "that kind of file and a stamp on it would be a claim about bytes nobody "
                       "checked" % (rel, contract.name, ", ".join(contract.fields) or "none"))
        return row
    want = expected_version(contract, root, cache)
    found = data.get(STAMP)
    row["found"] = found
    row["expected"] = want
    if found in (None, ""):
        row.update(state=MISSING, why=contract.why)
    elif str(found) == str(want):
        row.update(state=STAMPED, why=contract.why)
    else:
        row.update(state=STALE, why=contract.why)
    return row


def audit(root):
    """(rows, problems) -- one row per JSON file opened, so an omission is visible as one."""
    root = Path(root)
    cache = {}
    rows = [judge(rel, path, root, cache) for rel, path in json_files(root)]
    return rows, refusal_lines(rows)


def state_counts(rows):
    counts = dict((state, 0) for state in
                  (STAMPED, MISSING, STALE, NOT_GENERATED, OUT_OF_BOUNDARY, UNREADABLE,
                   UNCLASSIFIED))
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return counts


def expected_note(row):
    """What the contract says the version should be -- or, when it cannot say, why not."""
    return row["expected"] or ("nothing, because %s declares no %s" % (SYSTEM_JSON, STAMP))


def refusal_lines(rows):
    """Every refusal names its file; a count of problems with no list is the silent gate."""
    out = []
    for row in rows:
        if row["state"] not in REFUSAL_STATES:
            continue
        if row["state"] == MISSING:
            out.append("%s: written by %s under the %s contract and carries no %s — a reader "
                       "cannot tell which shape this file is in, so it can only guess (enter the "
                       "stamp: python scripts/schema_stamp.py --stamp --write)"
                       % (row["path"], row["writer"], row["contract"], STAMP))
        elif row["state"] == STALE:
            out.append("%s: carries %s=%s while the %s contract (written by %s) says %s — the "
                       "file was written by an older shape. Do not paint the number: regenerate "
                       "it with its writer, or amend it through that writer's own door"
                       % (row["path"], STAMP, row["found"], row["contract"], row["writer"],
                          expected_note(row)))
        elif row["state"] == UNREADABLE:
            out.append("%s: %s — a JSON file the gate cannot open is reported, never counted as "
                       "a file it did not have a problem with" % (row["path"], row["why"]))
        else:
            out.append("%s: %s" % (row["path"], row["why"]))
    return out


def format_row(row):
    """The enumeration line: state, path, contract, and the two numbers when both exist."""
    label = {STAMPED: "STAMPED   ", NOT_GENERATED: "AUTHORED  ",
             OUT_OF_BOUNDARY: "DISPOSABLE", MISSING: "INVALID   ", STALE: "INVALID   ",
             UNREADABLE: "INVALID   ", UNCLASSIFIED: "INVALID   "}
    head = "%s %s" % (label.get(row["state"], "UNKNOWN   "), row["path"])
    if row["state"] == STAMPED:
        return "%s  %s <- %s %s" % (head, row["contract"], row["writer"], row["expected"])
    if row["state"] == NOT_GENERATED:
        return "%s  %s — %s" % (head, row["contract"], row["why"])
    if row["state"] == STALE:
        return "%s  %s says %s, contract says %s" % (head, row["contract"], row["found"],
                                                     expected_note(row))
    if row["state"] == MISSING:
        return "%s  %s expects %s here, the key is absent" % (head, row["contract"],
                                                              row["expected"])
    return "%s  %s" % (head, row["why"])


def emit(rows):
    for row in rows:
        print(format_row(row))


# --- the writer's helper -----------------------------------------------------------------------
def stamp_payload(payload, contract_name, version=None):
    """A writer's one call: declare the contract this payload is written under.

    Returns a new dict with the stamp first; raises ValueError when the payload does not hold the
    fields the contract names -- stamping a file whose shape the gate cannot check would be a
    claim about bytes nobody measured.
    """
    contract = CONTRACT_BY_NAME.get(contract_name)
    if contract is None:
        raise ValueError("%r is not a contract this table owns (%s)"
                         % (contract_name, ", ".join(sorted(CONTRACT_BY_NAME))))
    if contract.kind == CONTRACT:
        raise ValueError("%s is hand-authored; a writer may not claim it" % contract_name)
    if version == CONFIG_VERSION:
        raise ValueError("%s: pass the number read from %s, not the marker %r"
                         % (contract_name, SYSTEM_JSON, CONFIG_VERSION))
    if version is None and contract.version == CONFIG_VERSION:
        raise ValueError("%s stamps the number %s declares; the writer must pass that version"
                         % (contract_name, SYSTEM_JSON))
    if version is None:
        version = contract.version
    if not contract.holds(dict((key, value) for key, value in payload.items()
                               if key != STAMP)):
        raise ValueError("a %s payload does not hold the fields its contract names (%s)"
                         % (contract_name, ", ".join(contract.fields)))
    ordered = {STAMP: version}
    ordered.update((key, value) for key, value in payload.items() if key != STAMP)
    return ordered


def stamp_target(row):
    """("stamp", version) / ("skip", why) / ("refuse", why) for one judged row."""
    if row["state"] == MISSING:
        return "stamp", row["expected"]
    if row["state"] == STALE:
        return "refuse", ("says %s while the %s contract says %s -- the file was written by an "
                          "older shape, and painting the number over it is the fabrication this "
                          "gate exists to catch: regenerate it with %s"
                          % (row["found"], row["contract"], expected_note(row), row["writer"]))
    if row["state"] in (UNREADABLE, UNCLASSIFIED):
        return "refuse", row["why"]
    if row["state"] == STAMPED:
        return "skip", "already stamped %s" % row["found"]
    return "skip", "%s (%s): %s" % (row["state"], row["contract"] or "no contract", row["why"])


INSERT_RE = re.compile(r"\{\r?\n([ \t]*)\"")


def stamp_text(text, version):
    """Insert the stamp as its own first line, changing nothing else.

    Shipped JSON is data a person or a tool already measured. Re-serialising it would sort keys,
    re-flow strings and move every byte, so a review could not tell the stamp from a rewrite;
    this adds one line and refuses any file whose bytes are not the one-key-per-line shape.
    """
    match = INSERT_RE.match(text)
    if not match:
        raise ValueError("its bytes are not the one-key-per-line shape a writer produces "
                         "(no opening brace on the first line, or a byte-order mark); stamping "
                         "it would mean re-serialising shipped data")
    indent, newline = match.group(1), ("\r\n" if text[1:3] == "\r\n" else "\n")
    line = '%s"%s": %s,%s' % (indent, STAMP, json.dumps(version), newline)
    return "{%s%s%s" % (newline, line, text[1 + len(newline):])


def migrate(root, write):
    """Pay the debt this gate names, one honest line at a time, or refuse with the reason."""
    rows, _problems = audit(root)
    paths = dict(json_files(root))
    targets, refused, skipped = [], [], []
    for row in rows:
        action, info = stamp_target(row)
        if action == "skip":
            skipped.append("%s: %s" % (row["path"], info))
            continue
        if action == "refuse":
            refused.append("%s: %s" % (row["path"], info))
            continue
        path = paths[row["path"]]
        text = path.read_bytes().decode("utf-8")
        try:
            new_text = stamp_text(text, info)
        except ValueError as exc:
            refused.append("%s: %s" % (row["path"], exc))
            continue
        after = json.loads(new_text)
        before = dict((key, value) for key, value in json.loads(text).items() if key != STAMP)
        rest = dict((key, value) for key, value in after.items() if key != STAMP)
        if after.get(STAMP) != info or rest != before:
            refused.append("%s: the stamped bytes do not parse back to the same content — "
                           "nothing was written" % row["path"])
            continue
        targets.append((row["path"], row["contract"], info, path, new_text))
    for rel, name, version, _path, _text in targets:
        print("%s  %s <- %s %s" % ("STAMP " if write else "WOULD ", rel, name, version))
    for line in skipped:
        print("SKIP    %s" % line)
    for line in refused:
        print("REFUSE  %s" % line)
    if refused:
        print("REFUSED: %d file(s) this command will not touch — a stamp entered over a file the "
              "contract does not own would be a claim about a shape nobody checked" % len(refused))
        return 1
    if not write:
        print("DRY RUN — %d file(s) would gain a stamp; re-run with --write" % len(targets))
        return 0
    for _rel, _name, _version, path, text in targets:
        path.write_bytes(text.encode("utf-8"))
    print("STAMPED %d file(s); %d named above needed nothing (already stamped, hand-authored, "
          "or disposable)" % (len(targets), len(skipped)))
    return 0


# --- the human-facing modes --------------------------------------------------------------------
def report_writers(root):
    """The table, with the count of files each row claims on this disk right now."""
    root = Path(root)
    cache = {}
    rows = [judge(rel, path, root, cache) for rel, path in json_files(root)]
    print("contracts this table owns (%s names the field written at):" % STAMP)
    for contract in CONTRACTS:
        claimed = [row for row in rows if row["contract"] == contract.name]
        print("  %-18s %-9s %-34s version %-8s %d file(s)"
              % (contract.name, contract.kind, contract.writer,
                 expected_version(contract, root, cache) or "(none)", len(claimed)))
    print("%d JSON file(s) on this disk: %d claimed above, %d by no contract at all"
          % (len(rows), len([r for r in rows if r["contract"]]),
             len([r for r in rows if r["contract"] is None])))
    return 0


def run_check(root, as_list=False):
    rows = audit(root)[0]
    emit(rows)
    counts = state_counts(rows)
    if as_list:
        return 0
    problems = refusal_lines(rows)
    if problems:
        print("REFUSED: %d of %d JSON file(s) cannot be trusted as written — each is named here "
              "with its contract, its state and what to do about it" % (len(problems), len(rows)))
        for line in problems:
            print("  %s" % line)
        return 1
    print("OK — %d JSON file(s) opened and judged by name: %d stamped, %d hand-authored, "
          "%d behind the git boundary, %d missing, %d stale, %d unreadable, %d claimed by no "
          "contract; every file above is named with its contract and its state"
          % (len(rows), counts[STAMPED], counts[NOT_GENERATED], counts[OUT_OF_BOUNDARY],
             counts[MISSING], counts[STALE], counts[UNREADABLE], counts[UNCLASSIFIED]))
    return 0


def main():
    parser = argparse.ArgumentParser(description="the schema_version gate for generated JSON")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--check", action="store_true",
                        help="refuse a missing or stale stamp; name every file it opened")
    parser.add_argument("--list", action="store_true", dest="as_list",
                        help="print the enumeration and exit 0")
    parser.add_argument("--writers", action="store_true",
                        help="print the contract table and what each row claims")
    parser.add_argument("--stamp", action="store_true",
                        help="enter a missing stamp (dry run without --write)")
    parser.add_argument("--write", action="store_true",
                        help="with --stamp: actually write the files")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))

    if args.write and not args.stamp:
        print("REFUSED: --write only means something beside --stamp; nothing was written")
        return 1
    if args.writers:
        return report_writers(root)
    if args.stamp:
        return migrate(root, args.write)
    return run_check(root, args.as_list)


if __name__ == "__main__":
    sys.exit(main())
