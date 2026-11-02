"""Phase 44 -- every generated JSON file says which contract wrote it, and a gate reads that.

A file with no version inside it can only be *guessed* at: the reader opens it, finds the keys it
remembers and calls the rest noise. When the writer's shape moves, the reader does not fail -- it
mis-parses quietly and prints a green result over a file it cannot see, which this repo's own law
calls a silent gate. So the stamp goes in at write time (`hades.py`'s one door, `loop.py`'s one
write, `schema_stamp.stamp_payload()` for any writer that wants it) and `scripts/schema_stamp.py`
refuses a missing or stale one.

The starting state was measured, not remembered: on 2026-11-02 a walk of `Path('.').rglob('*.json')`
printed `2 of 44`, and the same measure over `git ls-files "*.json"` printed `1 of 34`. After
`--stamp --write` paid that debt, the gate's own line -- the number worth quoting, because raw
counts drift while other writers run -- printed over the shipped tree:

    OK - 48 JSON file(s) opened and judged by name: 37 stamped, 11 hand-authored,
    0 behind the git boundary, 0 missing, 0 stale, 0 unreadable, 0 claimed by no contract

Every class below is red on the commit before the gate exists.

What each class holds the change to:
  * TestWritersStampAtWriteTime -- the real generators, run for real, put the number in.
  * TestTheAuditRefusesByName -- a missing, stale, unreadable or unclaimed file is refused, and
    the refusal names it; every file opened gets a line, so an omission is visible as one.
  * TestTheStampingMigrationIsHonest -- `--stamp` adds exactly one line, and refuses a file whose
    shape it cannot check, whose number it would have to paint over, or whose bytes it would have
    to re-serialise.
  * TestTheTableIsNotTwoTruths -- move the version in `system.json` and every file written against
    it goes stale by name: the number lives in one place, and the gate bites.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import loop  # noqa: E402
import schema_stamp  # noqa: E402
from common import run_utf8  # noqa: E402
from hades_fixture import seeded  # noqa: E402

GATE = str(SCRIPTS / "schema_stamp.py")
STAMP = schema_stamp.STAMP
PLANE_MAP = "15_SYSTEM/config/system.json"
RECORD_PATH = "11_CONTROL/skills/SKL-11111111-fixture/skill.json"
HISTORY_PATH = "14_CANDIDATES/loop/history.json"


def record_payload(version=None):
    """The shape `registry-record` names: a registry manifest, stamped or not."""
    data = {"id": "SKL-11111111", "kind": "skill", "name": "A fixture skill",
            "status": "draft", "classification": "public", "created_at": "2026-11-02",
            "description": "the fields registry-record names and nothing else"}
    if version is None:
        return data
    return dict([(STAMP, version)] + list(data.items()))


def fixture_root(root, version="3.0.0"):
    """A repo-shaped folder: the plane map plus the file under test, and nothing else."""
    root = Path(root)
    (root / "15_SYSTEM" / "config").mkdir(parents=True, exist_ok=True)
    write_json(root / PLANE_MAP, {STAMP: version, "kinds": {}, "zones": []})
    return root


def write_json(path, data, newline="\n"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return path


def gate(*args):
    return run_utf8([sys.executable, GATE] + list(args))


def check(root):
    return gate("--root", str(root), "--check")


def rows_by_path(root):
    return dict((row["path"], row) for row in schema_stamp.audit(root)[0])


def states(root):
    return dict((path, row["state"]) for path, row in rows_by_path(root).items())


def rows_of(state, root):
    return [row for row in schema_stamp.audit(root)[0] if row["state"] == state]


def metrics_for_a_ratchet(gaps=0):
    """The shape `loop.py`'s own collect() lays down, read from loop.py:256-266."""
    return {"link_check": {"problems": []}, "frontmatter_check": {"problems": []},
            "vault": {"stale_inbox": [], "awaiting_approval": []},
            "kb_gaps": {"open": gaps}, "hygiene": {"todo_hygiene": 0},
            "tests": {"returncode": 0, "summary": "skipped"}}


class TestWritersStampAtWriteTime(unittest.TestCase):
    """The generators, run for real, inside a throwaway vault -- not a mock of them."""

    def setUp(self):
        self.vault = seeded()
        self.version = self.vault.cfg[STAMP]

    def tearDown(self):
        self.vault.close()

    def test_every_json_hades_wrote_carries_the_number_the_plane_map_declares(self):
        self.assertTrue(self.version, "the fixture config declares no %s" % STAMP)
        code, out = self.vault.hades("index")
        self.assertEqual(0, code, out)
        rows, problems = schema_stamp.audit(self.vault.root)
        self.assertEqual([], problems, "\n".join(problems))
        by_state = {}
        for row in rows:
            by_state.setdefault(row["contract"], []).append(row["state"])
        for family in ("registry-record", "registry-plan", "registry-catalog"):
            self.assertIn(family, by_state, "the vault holds no %s file: %s" % (family, by_state))
            self.assertEqual({schema_stamp.STAMPED}, set(by_state[family]),
                             "a %s file written by hades.py carries no stamp: %s"
                             % (family, by_state[family]))
        stamped = [row for row in rows if row["state"] == schema_stamp.STAMPED]
        self.assertTrue(stamped, "nothing in the vault is stamped")
        for row in stamped:
            self.assertEqual(row["expected"], row["found"],
                             "%s says %s, its %s contract says %s" % (row["path"], row["found"],
                                                                      row["contract"],
                                                                      row["expected"]))
            if row["contract"].startswith("registry-"):
                self.assertEqual(self.version, row["expected"],
                                 "the %s contract typed a number instead of reading the plane "
                                 "map's" % row["contract"])

    def test_a_plan_written_for_review_is_stamped_before_anyone_approves_it(self):
        _code, out = self.vault.hades("plan", "--kind", "organization", "--name", "Planned Org",
                                      "--description", "fixture")
        plan_id = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        plan = json.loads((self.vault.root / "15_SYSTEM" / "generated" / "plans"
                           / (plan_id + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(self.version, plan.get(STAMP),
                         "a plan a person reviews carries no version, so they cannot tell which "
                         "shape it was written in: %s" % sorted(plan))

    def test_an_amendment_keeps_the_stamp_and_the_trail_and_still_passes_the_gate(self):
        _code, out = self.vault.hades("list", "--kind", "project")
        ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)
        _code, out = self.vault.hades("show", "--id", ident)
        path = self.vault.root / out.split("# file:")[-1].strip()
        before = json.loads(path.read_text(encoding="utf-8"))
        code, out = self.vault.hades("set", "--id", ident, "--field", "name",
                                     "--value", "Renamed By The Stamp Test")
        self.assertEqual(0, code, out)
        plan_id = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        code, out = self.vault.hades("apply", "--plan", plan_id, "--approve")
        self.assertEqual(0, code, out)
        after = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(self.version, after.get(STAMP), after)
        self.assertEqual(1, len(after.get("amendments") or []), after)
        self.assertEqual(before["created_at"], after["created_at"])
        self.assertEqual([], schema_stamp.audit(self.vault.root)[1],
                         "an approved amendment left a file the gate cannot vouch for")

    def test_a_person_cannot_type_the_number_into_a_record_to_quiet_the_gate(self):
        """Once `set` accepts the stamp, a red gate is one keystroke away -- the fabrication."""
        _code, out = self.vault.hades("list", "--kind", "project")
        ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)
        path = self.record_path(ident)
        before = path.read_bytes()
        code, out = self.vault.hades("set", "--id", ident, "--field", STAMP, "--value", '"9.9.9"')
        self.assertEqual(2, code, out)
        self.assertIn("REFUSED", out, out)
        self.assertEqual(before, path.read_bytes(), "the number was typed over the real one")

    def record_path(self, ident):
        _code, out = self.vault.hades("show", "--id", ident)
        return self.vault.root / out.split("# file:")[-1].strip()


class TestTheLoopWriter(unittest.TestCase):
    """`loop.py` owns one generated file and stamps it with its own literal shape version."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="phase44-loop-")
        self.root = fixture_root(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_history_written_by_the_ratchet_carries_its_version_first(self):
        path = self.root / HISTORY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        loop.ratchet(metrics_for_a_ratchet(), path)
        loop.ratchet(metrics_for_a_ratchet(gaps=1), path)
        text = path.read_text(encoding="utf-8")
        self.assertEqual(STAMP, list(json.loads(text))[0],
                         "the stamp is not the first key a reader sees: %s" % text.split("\n")[0])
        row = rows_by_path(self.root)[HISTORY_PATH]
        self.assertEqual(schema_stamp.STAMPED, row["state"], row)
        self.assertEqual("1", row["found"], row)
        self.assertEqual("loop-history", row["contract"])

    def test_the_gate_refuses_history_that_declares_no_shape(self):
        path = self.root / HISTORY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, {"runs": []})
        result = check(self.root)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(HISTORY_PATH, result.stdout)
        self.assertEqual(schema_stamp.MISSING, states(self.root)[HISTORY_PATH])


class TestTheAuditRefusesByName(unittest.TestCase):
    """House law: an audit enumerates the files it looked at and names each one's state."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="phase44-audit-")
        self.root = fixture_root(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_missing_stamp_is_refused_and_the_file_is_named_with_its_writer(self):
        write_json(self.root / RECORD_PATH, record_payload())
        result = check(self.root)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(RECORD_PATH, result.stdout)
        self.assertIn("registry-record", result.stdout)
        self.assertIn("hades.py", result.stdout)
        self.assertIn("--stamp --write", result.stdout,
                      "a refusal that does not say how to pay the debt is a dead end")

    def test_a_stale_stamp_is_refused_and_told_to_regenerate_not_repaint(self):
        write_json(self.root / RECORD_PATH, record_payload("0.0.1"))
        rows, problems = schema_stamp.audit(self.root)
        row = [r for r in rows if r["path"] == RECORD_PATH][0]
        self.assertEqual(schema_stamp.STALE, row["state"], row)
        self.assertEqual("0.0.1", row["found"])
        self.assertEqual("3.0.0", row["expected"])
        self.assertEqual(1, len(problems), problems)
        self.assertIn(RECORD_PATH, problems[0])
        self.assertIn("Do not paint the number", problems[0], problems[0])
        result = check(self.root)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("INVALID", result.stdout)
        self.assertIn("says 0.0.1", result.stdout, result.stdout)

    def test_a_file_that_is_not_the_shape_its_contract_names_is_refused_not_assumed(self):
        write_json(self.root / RECORD_PATH, {"id": "SKL-11111111", "kind": "skill"})
        row = rows_by_path(self.root)[RECORD_PATH]
        self.assertEqual(schema_stamp.UNCLASSIFIED, row["state"], row)
        result = check(self.root)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(RECORD_PATH, result.stdout)

    def test_a_json_file_the_gate_cannot_open_is_reported_not_counted_as_absent(self):
        path = self.root / RECORD_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"id": "SKL-11111111", "kind": ', encoding="utf-8")
        self.assertEqual(schema_stamp.UNREADABLE, states(self.root)[RECORD_PATH])
        result = check(self.root)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(RECORD_PATH, result.stdout)
        self.assertIn("is not JSON", result.stdout, result.stdout)

    def test_a_file_no_contract_claims_is_a_refusal_because_a_clone_carries_it(self):
        write_json(self.root / "02_WIKI/mystery.json", {"whatever": 1})
        row = rows_by_path(self.root)["02_WIKI/mystery.json"]
        self.assertEqual(schema_stamp.UNCLASSIFIED, row["state"], row)
        self.assertEqual(1, len(schema_stamp.audit(self.root)[1]))

    def test_a_disposable_file_behind_the_git_boundary_is_named_with_its_reason(self):
        """Not a skip -- a skip would be the silent gate -- and not a refusal a clone cannot fix."""
        write_json(self.root / "12_RUNTIME/state.json", {"whatever": 1})
        row = rows_by_path(self.root)["12_RUNTIME/state.json"]
        self.assertEqual(schema_stamp.OUT_OF_BOUNDARY, row["state"], row)
        self.assertIn("common.clone_readable", row["why"])
        result = check(self.root)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("DISPOSABLE 12_RUNTIME/state.json", result.stdout, result.stdout)

    def test_every_json_file_opened_gets_a_line_so_an_omission_is_visible(self):
        write_json(self.root / RECORD_PATH, record_payload())
        write_json(self.root / HISTORY_PATH, {"runs": []})
        write_json(self.root / "12_RUNTIME/state.json", {"whatever": 1})
        opened = [rel for rel, _path in schema_stamp.json_files(self.root)]
        rows, _problems = schema_stamp.audit(self.root)
        self.assertEqual(sorted(opened), sorted(r["path"] for r in rows),
                         "the gate printed a verdict on files it did not open, or stayed quiet "
                         "on files it did")
        listed = gate("--root", str(self.root), "--list")
        self.assertEqual(0, listed.returncode, listed.stdout)
        lines = [line for line in listed.stdout.splitlines()
                 if re.match(r"^(STAMPED|AUTHORED|DISPOSABLE|INVALID) ", line)]
        self.assertEqual(len(opened), len(lines),
                          "%d file(s) opened, %d line(s) printed:\n%s"
                          % (len(opened), len(lines), listed.stdout))

    def test_the_ok_line_counts_every_state_it_judged(self):
        write_json(self.root / RECORD_PATH, record_payload("3.0.0"))
        write_json(self.root / "rules/zones.json", {"zones": []})
        result = check(self.root)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("OK", result.stdout)
        for state in ("stamped", "hand-authored", "behind the git boundary", "missing", "stale",
                      "unreadable"):
            self.assertIn(state, result.stdout, result.stdout)

    def test_the_shipped_tree_passes_the_gate_and_no_generated_file_is_left_unstamped(self):
        result = check(ROOT)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        rows = schema_stamp.audit(ROOT)[0]
        self.assertTrue(rows, "the gate opened no file at all")
        unstamped = [r["path"] for r in rows
                     if r["kind"] in (schema_stamp.GENERATED, schema_stamp.LEDGER)
                     and r["state"] != schema_stamp.STAMPED]
        self.assertEqual([], unstamped, "these generated files carry no shape declaration")
        unexplained = [r["path"] for r in rows if r["state"] == schema_stamp.NOT_GENERATED
                       and not r["why"]]
        self.assertEqual([], unexplained,
                         "hand-authored files must be classified by name WITH a reason, not "
                         "skipped silently")


class TestTheStampingMigrationIsHonest(unittest.TestCase):
    """The one command that pays the debt; it may add a line and nothing else."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="phase44-migrate-")
        self.root = fixture_root(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stamp(self, *extra):
        return gate("--root", str(self.root), "--stamp", *extra)

    def test_it_adds_exactly_one_line_and_changes_no_other_byte(self):
        path = write_json(self.root / RECORD_PATH, record_payload())
        before = path.read_bytes().decode("utf-8")
        result = self.stamp("--write")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("STAMPED 1 file(s)", result.stdout, result.stdout)
        after = path.read_bytes().decode("utf-8")
        self.assertTrue(after.startswith('{\n  "%s": "3.0.0",\n' % STAMP), after[:80])
        self.assertEqual(before, after.replace('  "%s": "3.0.0",\n' % STAMP, "", 1),
                         "more than the stamp moved")
        self.assertEqual([STAMP], list(json.loads(after))[:1])
        self.assertEqual(0, check(self.root).returncode)

    def test_a_dry_run_names_the_file_and_writes_nothing(self):
        path = write_json(self.root / RECORD_PATH, record_payload())
        before = path.read_bytes()
        result = self.stamp()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("WOULD   %s <- registry-record 3.0.0" % RECORD_PATH, result.stdout)
        self.assertIn("DRY RUN", result.stdout)
        self.assertEqual(before, path.read_bytes(), "a dry run wrote bytes")

    def test_it_refuses_a_stale_file_rather_than_painting_the_number_over_it(self):
        path = write_json(self.root / RECORD_PATH, record_payload("0.0.1"))
        before = path.read_bytes()
        result = self.stamp("--write")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSE", result.stdout)
        self.assertIn(RECORD_PATH, result.stdout)
        self.assertIn("regenerate it with", result.stdout, result.stdout)
        self.assertEqual(before, path.read_bytes(),
                         "the gate's number was painted over a stale one")

    def test_it_refuses_a_file_whose_shape_the_contract_does_not_own(self):
        path = write_json(self.root / RECORD_PATH, {"id": "SKL-11111111", "kind": "skill"})
        before = path.read_bytes()
        result = self.stamp("--write")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(RECORD_PATH, result.stdout)
        self.assertEqual(before, path.read_bytes())

    def test_it_refuses_bytes_it_could_only_stamp_by_re_writing_them(self):
        path = self.root / RECORD_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record_payload()), encoding="utf-8")
        before = path.read_bytes()
        result = self.stamp("--write")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("one-key-per-line", result.stdout, result.stdout)
        self.assertEqual(before, path.read_bytes(),
                         "shipped data was re-serialised to squeeze a stamp in")

    def test_a_crlf_file_stays_a_crlf_file(self):
        path = write_json(self.root / RECORD_PATH, record_payload(), newline="\r\n")
        self.assertEqual(0, self.stamp("--write").returncode)
        data = path.read_bytes()
        self.assertIn(b'\r\n', data)
        self.assertNotIn(b'\n\x20', data.replace(b'\r\n', b''),
                         "a lone LF joined a CRLF file")
        self.assertEqual("3.0.0", json.loads(data.decode("utf-8"))[STAMP])

    def test_write_alone_refuses_before_it_can_touch_anything(self):
        result = gate("--root", str(self.root), "--write")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSED", result.stdout)


class TestTheTableIsNotTwoTruths(unittest.TestCase):
    """The version lives in the plane map; the gate bites when it moves."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="phase44-table-")
        self.root = fixture_root(Path(self.tmp) / "repo")
        self.path = write_json(self.root / RECORD_PATH, record_payload("3.0.0"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_moving_the_version_in_the_plane_map_makes_the_stamped_file_stale_by_name(self):
        """The bite, proved once: no grandfather branch, no silent acceptance of the old shape."""
        self.assertEqual(0, check(self.root).returncode)
        write_json(self.root / PLANE_MAP, {STAMP: "4.0.0", "kinds": {}, "zones": []})
        row = rows_by_path(self.root)[RECORD_PATH]
        self.assertEqual(schema_stamp.STALE, row["state"], row)
        self.assertEqual("4.0.0", row["expected"], "the expected number came from nowhere")
        result = check(self.root)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(RECORD_PATH, result.stdout)

    def test_a_missing_plane_map_version_is_a_refusal_not_a_default(self):
        write_json(self.root / PLANE_MAP, {"kinds": {}, "zones": []})
        row = rows_by_path(self.root)[RECORD_PATH]
        self.assertEqual(schema_stamp.STALE, row["state"], row)
        self.assertIsNone(row["expected"], row)

    def test_a_writer_cannot_claim_a_hand_authored_contract(self):
        for name in ("workflow-body", "zone-law", "plane-map"):
            with self.assertRaises(ValueError) as caught:
                schema_stamp.stamp_payload({"steps": []}, name)
            self.assertIn("hand-authored", str(caught.exception))

    def test_a_writer_must_pass_the_number_the_plane_map_declares(self):
        with self.assertRaises(ValueError):
            schema_stamp.stamp_payload(record_payload(), "registry-record")
        with self.assertRaises(ValueError) as caught:
            schema_stamp.stamp_payload(record_payload(), "registry-record",
                                       schema_stamp.CONFIG_VERSION)
        self.assertIn(PLANE_MAP, str(caught.exception))
        stamped = schema_stamp.stamp_payload(record_payload(), "registry-record", "3.0.0")
        self.assertEqual("3.0.0", stamped[STAMP])
        self.assertEqual([STAMP], list(stamped)[:1])

    def test_a_payload_that_is_not_the_shape_cannot_be_stamped(self):
        with self.assertRaises(ValueError) as caught:
            schema_stamp.stamp_payload({"id": "SKL-11111111", "kind": "skill"},
                                       "registry-record", "3.0.0")
        self.assertIn("registry-record", str(caught.exception))

    def test_the_registry_stamp_and_the_hades_plan_are_one_table_not_two(self):
        """`--writers` is the whole claim; a file nobody claims is stated as such."""
        write_json(self.root / "02_WIKI/mystery.json", {"whatever": 1})
        result = gate("--root", str(self.root), "--writers")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("registry-record", result.stdout)
        self.assertIn("loop-history", result.stdout)
        self.assertIn("issue-ledger", result.stdout)
        self.assertIn("1 by no contract at all", result.stdout, result.stdout)

    def test_the_sqlite_index_version_is_not_this_kind_of_stamp(self):
        """kb.py's SCHEMA is a rebuilt index's shape tag; conflating them would fake coverage."""
        kb = (SCRIPTS / "kb.py").read_text(encoding="utf-8")
        self.assertRegex(kb, r'SCHEMA\s*=\s*"2"')
        self.assertEqual([], [c.name for c in schema_stamp.CONTRACTS if c.version == "2"],
                         "a JSON contract now stamps the sqlite index's number")


if __name__ == "__main__":
    unittest.main()
