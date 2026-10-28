"""The eight memory planes must open where this file lives — repo or installed home.

`scripts/install.py` ships this file into every installed brain, because the source map names
the source repo's tests and a home has none of them. So the same proof runs twice: in the
source repo (`plane_check` judges it there too) and in a fresh home, where it is the only
evidence that the declared stores, readers and map were really laid down.

Usage: python -m unittest discover -s tests
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import run_utf8  # noqa: E402

PLANES = ("project", "repository", "agent", "task", "error", "decision", "knowledge",
          "conversation")
PROOF = "tests/test_installed_home.py"


def config():
    return json.loads((ROOT / "15_SYSTEM" / "config" / "system.json").read_text(encoding="utf-8"))


class TheEightPlanesOpen(unittest.TestCase):
    def test_every_plane_has_its_store_its_reader_and_its_map(self):
        planes = config().get("memory_planes") or {}
        self.assertEqual(sorted(planes), sorted(PLANES))
        for name in PLANES:
            spec = planes[name]
            for rel in spec.get("tracked_store") or []:
                path = ROOT / rel
                self.assertTrue(path.exists(), "%s: store missing: %s" % (name, rel))
                if path.is_dir():
                    self.assertTrue(any(path.iterdir()),
                                    "%s: store is an empty folder: %s" % (name, rel))
            reader = spec.get("reader_script") or spec.get("reader_doc")
            self.assertTrue(reader and (ROOT / reader).is_file(),
                            "%s: reader missing: %s" % (name, reader))
            self.assertTrue((ROOT / spec["map"]).is_file(),
                            "%s: map missing: %s" % (name, spec["map"]))

    def test_an_installed_home_names_this_file_as_its_proof(self):
        """A home that copies the source map would claim tests it does not ship."""
        cfg = config()
        if not cfg.get("home"):
            self.skipTest("source repo: the map names the repo's own tests")
        for name, spec in (cfg.get("memory_planes") or {}).items():
            self.assertEqual(spec.get("test"), PROOF, "%s still names a source test" % name)
        self.assertTrue((ROOT / PROOF).is_file(), "the proof this map names is not here")

    def test_the_registry_door_answers_in_this_brain(self):
        hades = ROOT / "15_SYSTEM" / "scripts" / "hades.py"
        self.assertTrue(hades.is_file(), "15_SYSTEM/scripts/hades.py is not in this brain")
        result = run_utf8([sys.executable, str(hades), "list"], cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("records:", result.stdout)

    def test_the_lesson_ledger_matches_its_rendered_index(self):
        result = run_utf8([sys.executable, str(ROOT / "scripts" / "memory.py"), "--check"],
                          cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_gates_can_run_here(self):
        """Every gate file the health command names is present; health itself is the wrap-up."""
        health = (ROOT / "scripts" / "health.py").read_text(encoding="utf-8")
        for gate in ("link_check.py", "frontmatter_check.py", "plane_check.py",
                     "candidate_check.py", "memory.py", "sync_hosts.py", "doc_report.py",
                     "vector_check.py"):
            self.assertIn(gate, health)
            self.assertTrue((ROOT / "scripts" / gate).is_file(), "%s is not here" % gate)


if __name__ == "__main__":
    unittest.main()
