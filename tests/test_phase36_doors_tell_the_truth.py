"""Phase 36 — the doors stop flattering themselves: issues #15, #16 and #17.

Three reports shared one shape: a check that was true was described by a sentence that was
not, so the repo could be green and wrong at the same time.

  1. #15 `state_fingerprint` counted `15_SYSTEM/generated/`, so one `hades.py index` aged
     every recorded probe and no clone could reproduce a saved base;
  2. #16 a refused export called a `plane: human` zone "the denied machine plane", and three
     documents narrowed the deny set to a subfolder the config never named;
  3. #17 `memory.py --add --supersedes <unknown>` wrote the row and left `--check` to refuse
     a lesson that was already in the ledger and already rendered.

Each class below is red on the commit before its fix.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hades_fixture import seeded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
import common  # noqa: E402
from common import run_utf8, state_fingerprint  # noqa: E402

MEMORY = str(SCRIPTS / "memory.py")
CONFIG = "15_SYSTEM/config/system.json"
DOCS = ("AGENTS.md", "00_START_HERE/ACCESS.md", "00_START_HERE/SYSTEM_MAP.md")
ZONE_TOKEN = re.compile(r"`([0-9]{2}_[A-Z_]+(?:/[a-z_]+)?)`")


class FingerprintIsTheBrainNotItsPaperwork(unittest.TestCase):
    """#15 — regenerated output is paperwork, so it cannot move the identity."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "README.md").write_text("the brain", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_an_index_run_does_not_age_a_probe(self):
        before = state_fingerprint(self.root)
        generated = self.root / "15_SYSTEM" / "generated" / "catalog.json"
        generated.parent.mkdir(parents=True)
        generated.write_text(json.dumps({"catalog": "rebuilt"}), encoding="utf-8")
        (generated.parent / "plans").mkdir()
        (generated.parent / "plans" / "PLAN-1.json").write_text("{}", encoding="utf-8")
        self.assertEqual(before, state_fingerprint(self.root),
                         "15_SYSTEM/generated/ is regenerated output, not state")

    def test_the_identity_still_sees_a_real_edit(self):
        before = state_fingerprint(self.root)
        (self.root / "README.md").write_text("the brain, edited", encoding="utf-8")
        self.assertNotEqual(before, state_fingerprint(self.root))


class ARefusalNamesTheRuleThatFired(unittest.TestCase):
    """#16 — the refusal must be literally true about the zone it refuses."""

    def setUp(self):
        self.vault = seeded()
        self.vault.write("09_OPERATIONS/README.md", "client operations")
        self.config = json.loads((ROOT / CONFIG).read_text(encoding="utf-8"))

    def tearDown(self):
        self.vault.close()

    def test_a_human_zone_is_not_called_a_machine_plane(self):
        code, out = self.vault.hades("export", "--path", "09_OPERATIONS/README.md")
        self.assertEqual(2, code, out)
        self.assertIn("REFUSED", out)
        self.assertIn("denied_for_default_context", out,
                      "the sentence must name the flag that fired: %s" % out)
        self.assertIn('"plane": "human"', out,
                      "09_OPERATIONS declares plane: human; the reason must say so: %s" % out)
        self.assertNotIn("denied machine plane", out)

    def test_the_machine_plane_reason_names_the_machine_plane(self):
        code, out = self.vault.hades("export", "--path", "12_RUNTIME")
        self.assertEqual(2, code, out)
        self.assertIn('"plane": "machine"', out, out)

    def test_generated_output_is_refused_as_generated(self):
        self.vault.write("15_SYSTEM/generated/catalog.json", "{}")
        code, out = self.vault.hades("export", "--path", "15_SYSTEM/generated/catalog.json")
        self.assertEqual(2, code, out)
        self.assertIn("generated_denied", out, out)

    def test_the_documents_deny_exactly_what_the_config_denies(self):
        wanted = set()
        for zone in self.config["zones"]:
            if zone.get("denied_for_default_context"):
                wanted.add(zone["dir"])
            if zone.get("generated_denied"):
                wanted.add(zone["dir"] + "/generated")
        for rel in DOCS:
            line = next((text for text in (ROOT / rel).read_text(encoding="utf-8").splitlines()
                         if "denied" in text.lower() or "ممنوع" in text), "")
            self.assertTrue(line, "%s never states the deny set" % rel)
            tokens = set(ZONE_TOKEN.findall(line))
            for prefix in wanted:
                self.assertTrue(prefix in tokens,
                                "%s does not deny %s (it lists %s)" % (rel, prefix, sorted(tokens)))
            for token in tokens:
                narrowed = [p for p in wanted if p.startswith(token + "/")]
                self.assertFalse(narrowed,
                                 "%s narrows %s to %s — the config denies the whole zone"
                                 % (rel, narrowed, token))

    def test_the_fix_widened_nothing(self):
        from hades import denied_prefixes, is_denied
        prefixes = denied_prefixes(self.config)
        self.assertIn("09_OPERATIONS", prefixes)
        for path in ("09_OPERATIONS/README.md", "09_OPERATIONS/clients_metadata_only/x.md",
                     "12_RUNTIME/state.json", "13_LAB/run.txt", "14_CANDIDATES/c.md",
                     "15_SYSTEM/generated/catalog.json"):
            self.assertTrue(is_denied(path, self.config), path)


class RetirementIsCheckedAtTheDoor(unittest.TestCase):
    """#17 — a `supersedes` that names nothing retires nothing."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "README.md").write_text("evidence", encoding="utf-8")
        (self.root / "rules").mkdir()
        shutil.copy(ROOT / "rules" / "memory.schema.json", self.root / "rules")

    def tearDown(self):
        self._tmp.cleanup()

    def memory(self, *args):
        done = run_utf8([sys.executable, MEMORY, "--root", str(self.root)] + list(args),
                        cwd=str(ROOT))
        return done.returncode, done.stdout

    def add(self, ident, *extra):
        return self.memory("--add", "--id", ident, "--cue", "a cue", "--lesson", "a lesson",
                           "--evidence", "README.md", "--confidence", "0.6",
                           "--verdict", "helped", *extra)

    def test_an_unknown_supersedes_is_refused_before_the_write(self):
        code, out = self.add("mem-new", "--supersedes", "mem-does-not-exist")
        self.assertEqual(1, code, out)
        self.assertIn("REFUSED", out)
        ledger = self.root / "15_SYSTEM" / "memory" / "lessons.jsonl"
        self.assertFalse(ledger.exists(), "a refused row must not be written")
        self.assertFalse((self.root / "MEMORY.md").exists(),
                         "and MEMORY.md must not be rendered around it")
        # the door is the only thing that ran: one honest row still leaves a green ledger
        self.assertEqual(0, self.add("mem-honest")[0])
        check, out = self.memory("--check")
        self.assertEqual(0, check, out)

    def test_a_row_cannot_retire_itself(self):
        code, out = self.add("mem-self", "--supersedes", "mem-self")
        self.assertEqual(1, code, out)
        self.assertIn("REFUSED", out)

    def test_superseding_a_row_the_ledger_holds_is_accepted(self):
        self.assertEqual(0, self.add("mem-old")[0])
        code, out = self.add("mem-new", "--supersedes", "mem-old")
        self.assertEqual(0, code, out)
        self.assertIn("ADDED mem-new", out)
        self.assertEqual(0, self.memory("--check")[0])


if __name__ == "__main__":
    unittest.main()
