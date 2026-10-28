"""Phase 24 -- one file, one contract: a registry record is not judged as a broken note.

`apply` writes a `wiki_note` / `news` record as markdown into a human zone (`02_WIKI`,
`04_INTELLIGENCE`), and the installed brain scans its own root with `--vault .`, so that file
is read by the note gate as well as by the registry. Measured on this repo, after the first
decision record was filed:

    python scripts/frontmatter_check.py --vault .
    INVALID 02_WIKI/decisions/WIK-....md: missing field: type / title / owner / topics / ...
    INVALID 02_WIKI/decisions/WIK-....md: invalid status: 'draft' (allowed: [inbox, raw, ...])

Two contracts claiming one file. The tempting fix -- have `to_markdown` also write `title`,
`type`, `created` and a second `status` drawn from the note enum -- would put two names on the
same field, and a record whose registry status says `approved` while its note status says
`raw` is exactly the duplicate truth the rest of this repo deletes. So the gate decides which
contract a file is under from the file's own content, using the recognizer the registry
already uses (a registry-shaped `id` *and* a declared `kind`: see phase 21).

This is not a hole: a record is still refused -- by the contract it actually claims. Its
status has to be one its kind allows *in the config*, its identity fields have to exist, and a
note that only pretends to be a record falls back to the note schema and fails there.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATE_RE, parse_frontmatter, run_utf8  # noqa: E402
import frontmatter_check  # noqa: E402
from hades_fixture import Vault  # noqa: E402

CHECK = str(SCRIPTS / "frontmatter_check.py")

RECORD = """---
id: "WIK-AAAAAAAA"
kind: "wiki_note"
name: "A definition, not a note"
status: "draft"
classification: "internal"
created_at: "2026-10-27"
last_verified: "2026-10-27"
topic: "decision"
tags: []
notes: "the body of the definition"
relations: {}
---

# A definition, not a note

the body of the definition
"""


def check(vault):
    return run_utf8([sys.executable, CHECK, "--vault", str(vault)], cwd=str(ROOT))


def note(**overrides):
    """Frontmatter-only markdown: the fields the note schema owns, all present."""
    fm = {"id": "note-1", "type": "note", "title": "Plain note", "status": "raw",
          "owner": "human", "topics": ["general"], "created": "2026-10-27",
          "updated": "2026-10-27"}
    fm.update(overrides)
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in fm.items()] + ["---", "", "body", ""]
    return "\n".join(lines)


class TestTheGatePicksTheContractFromTheFile(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def write(self, rel, text):
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_registry_record_in_a_human_zone_passes_the_note_gate(self):
        self.write("02_WIKI/decisions/WIK-AAAAAAAA-a-definition.md", RECORD)
        result = check(self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_a_record_status_outside_its_kind_is_still_refused(self):
        """`refined` is legal for a note and illegal for a wiki_note: the gate must say so."""
        self.write("02_WIKI/decisions/WIK-AAAAAAAA-a-definition.md",
                   RECORD.replace('status: "draft"', 'status: "refined"'))
        result = check(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("INVALID", result.stdout)
        self.assertIn("status", result.stdout)
        # the allowed set comes from the registry config, not from a list typed in the gate
        cfg = frontmatter_check.registry_contract(ROOT)
        self.assertTrue(cfg, "the gate cannot see the registry contract")
        for status in cfg["status_sets"].get("wiki_note", cfg["status_sets"]["default"]):
            self.assertIn(status, result.stdout,
                          "the refusal did not name the kind's own statuses: %s" % result.stdout)

    def test_a_record_missing_its_identity_is_refused_by_the_registry_contract(self):
        self.write("02_WIKI/decisions/WIK-AAAAAAAA-a-definition.md",
                   re.sub(r'^name: .*$', '', RECORD, flags=re.M))
        result = check(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("name", result.stdout)
        self.assertNotIn("missing field: title", result.stdout,
                         "a record was reported against the note fields it does not claim")

    def test_a_note_is_still_judged_as_a_note(self):
        self.write("20_Notes/good.md", note())
        self.write("20_Notes/bad.md", note(title=None, owner="robot"))
        result = check(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("bad.md", result.stdout)
        self.assertIn("owner", result.stdout)

    def test_a_note_that_only_claims_a_kind_is_refused_as_an_orphan(self):
        """A file between two contracts is invisible to one of them, so the gate names it."""
        self.write("20_Notes/pretender.md", note(kind="wiki_note"))
        result = check(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("pretender.md", result.stdout)
        self.assertIn("cannot enumerate", result.stdout, result.stdout)

    def test_the_recognizer_is_the_one_the_registry_already_uses(self):
        """One recognizer for both gates: no file may be a record to one and a note to the other."""
        sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
        import hades
        cfg = hades.config()
        registry = frontmatter_check.registry_contract(ROOT)
        enumerated = {hades.rel(p): p for p, _rec in hades.iter_records(cfg)
                      if str(p).endswith(".md")}
        for rel_path, path in enumerated.items():
            fm, _rest = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            self.assertTrue(frontmatter_check.is_registry_record(fm, registry),
                            "%s is a record to the registry and a note to the gate" % rel_path)
        wiki_from_hades = [r for r in enumerated if r.startswith("02_WIKI/")]
        wiki_from_gate = set()
        for path in (ROOT / "02_WIKI").rglob("*.md"):
            fm, _rest = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            if frontmatter_check.is_registry_record(fm, registry):
                wiki_from_gate.add(hades.rel(path))
        self.assertEqual(sorted(wiki_from_hades), sorted(wiki_from_gate),
                         "the two gates disagree about which files in 02_WIKI are records")


class TestTheRealRepoPassesItsOwnScan(unittest.TestCase):
    def test_the_human_plane_of_this_repo_is_valid_under_both_contracts(self):
        """How an installed brain reads itself: --vault . over the root, records included."""
        result = check(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_decision_record_this_repo_filed_is_seen_by_both_gates(self):
        records = sorted(ROOT.glob("02_WIKI/decisions/*.md"))
        self.assertTrue(records, "this repo filed no decision record, so the regression is untested")
        cfg = frontmatter_check.registry_contract(ROOT)
        for path in records:
            fm, _rest = parse_frontmatter(path.read_text(encoding="utf-8"))
            self.assertTrue(frontmatter_check.is_registry_record(fm, cfg),
                            "%s is a record the note gate still treats as a note" % path)


class TestWhatTheWriterProducesIsWhatTheReaderAccepts(unittest.TestCase):
    def test_a_record_written_by_apply_passes_the_note_gate(self):
        """The end-to-end law: `apply` writes, the gate reads -- same bytes, no hand-editing."""
        vault = Vault()
        try:
            code, out = vault.hades("new", "--kind", "wiki_note", "--name", "Gate Law",
                                    "--description", "a definition", "--category", "concept",
                                    "--approve")
            self.assertEqual(code, 0, out)
            written = [p for p in vault.root.rglob("*.md")
                       if re.match(r"^WIK-[0-9A-F]{8}-", p.name)]
            self.assertTrue(written, "no markdown record was written: %s" % out)
            result = check(vault.root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            vault.close()


class TestTheLawIsOwnedByTheRulesNotByTheCode(unittest.TestCase):
    def test_the_schema_names_the_contract_a_record_is_judged_by(self):
        schema = (ROOT / "rules" / "schema.json").read_text(encoding="utf-8")
        self.assertIn("record_contract", schema,
                      "rules/schema.json still claims every markdown is a note")
        self.assertIn("15_SYSTEM/config/system.json", schema)

    def test_the_canon_states_that_a_record_is_not_a_note(self):
        canon = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("one contract", canon.lower())

    def test_the_record_fields_come_from_the_registry_schema_not_a_second_list(self):
        cfg = frontmatter_check.registry_contract(ROOT)
        manifest = (ROOT / "15_SYSTEM" / "schemas" / "manifest.schema.json")
        import json
        required = json.loads(manifest.read_text(encoding="utf-8"))["common_required"]
        self.assertEqual(sorted(cfg["common_required"]), sorted(required),
                         "the note gate grew its own copy of the record's required fields")

    def test_the_recognizer_matches_the_registry_id_pattern(self):
        cfg = frontmatter_check.registry_contract(ROOT)
        self.assertTrue(re.match(cfg["id_pattern"], "WIK-B7ED0084"))
        self.assertFalse(re.match(cfg["id_pattern"], "note-1"))
        self.assertTrue(DATE_RE.match("2026-10-27"))


if __name__ == "__main__":
    unittest.main()
