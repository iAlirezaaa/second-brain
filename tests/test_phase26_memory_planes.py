"""Phase 26 — the eight memory planes are mapped, and the map cannot rot silently.

Charter section 5 names eight planes. Before this phase the stores existed but nothing
said which store carried which plane, nothing failed when one disappeared, and two of the
charter's adjectives ("searchable", "contradiction-aware") were only partly true. This
suite ties the claims to evidence:

  1. `15_SYSTEM/config/system.json` maps exactly the charter's eight names, and every
     tracked store, reader, test and map it names opens in this clone;
  2. `scripts/plane_check.py` is green here and red when a tracked store is deleted, a
     plane is dropped from the config, or a reader points at nothing;
  3. a disposable store (12_RUNTIME, .brain-data, .kb) is never required, because a fresh
     clone is supposed to lack it;
  4. the mapping document names every plane and every tracked store, so the two cannot
     drift apart.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
GATE = str(SCRIPTS / "plane_check.py")
CONFIG = ROOT / "15_SYSTEM" / "config" / "system.json"
MAP = ROOT / "02_WIKI" / "reference_maps" / "eight-memory-planes.md"
PLANES = ("project", "repository", "agent", "task", "error", "decision", "knowledge",
          "conversation")

sys.path.insert(0, str(SCRIPTS))
from common import run_utf8  # noqa: E402


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


class TestTheMapIsComplete(unittest.TestCase):
    def test_the_config_maps_exactly_the_charter_planes(self):
        mapped = set(config()["memory_planes"])
        self.assertEqual(set(PLANES), mapped,
                         "config and charter disagree: %s" % (set(PLANES) ^ mapped))

    def test_every_tracked_store_reader_test_and_map_opens_here(self):
        for name, spec in config()["memory_planes"].items():
            self.assertTrue(spec.get("tracked_store"), "%s has no tracked store" % name)
            for rel in spec["tracked_store"]:
                self.assertTrue((ROOT / rel).exists(), "%s: %s is missing" % (name, rel))
            reader = spec.get("reader_script") or spec.get("reader_doc")
            self.assertTrue((ROOT / reader).is_file(), "%s: reader %s is missing" % (name, reader))
            self.assertTrue((ROOT / spec["test"]).is_file(), "%s: test is missing" % name)
            self.assertTrue((ROOT / spec["map"]).is_file(), "%s: map is missing" % name)

    def test_the_gate_is_green_on_the_shipped_repo(self):
        result = run_utf8([sys.executable, GATE], cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("8 memory planes mapped", result.stdout)

    def test_the_map_document_names_every_plane_and_store(self):
        text = MAP.read_text(encoding="utf-8")
        for name in PLANES:
            self.assertIn("| %s |" % name, text, "the map has no row for %s" % name)
        for name, spec in config()["memory_planes"].items():
            for rel in spec["tracked_store"]:
                self.assertIn(rel, text, "%s: store %s is not in the map" % (name, rel))
            self.assertIn(spec["test"], text, "%s: test %s is not cited" % (name, spec["test"]))


class TestTheGateBites(unittest.TestCase):
    def fixture(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        cfg = config()
        (tmp / "15_SYSTEM" / "config").mkdir(parents=True)
        (tmp / "15_SYSTEM" / "config" / "system.json").write_text(
            json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        for spec in cfg["memory_planes"].values():
            for rel in spec["tracked_store"]:
                target = tmp / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.suffix:
                    target.write_text("x\n", encoding="utf-8")
                else:
                    target.mkdir(exist_ok=True)
                    (target / ".gitkeep").write_text("", encoding="utf-8")
            for field in ("reader_script", "reader_doc", "test", "map"):
                rel = spec.get(field)
                if rel:
                    (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                    (tmp / rel).write_text("x\n", encoding="utf-8")
        return tmp

    def run_gate(self, root):
        return run_utf8([sys.executable, GATE, "--vault", str(root)], cwd=str(ROOT))

    def test_a_fixture_with_no_disposable_state_is_green(self):
        """A fresh clone has no 12_RUNTIME, .brain-data or .kb; that must not be a defect."""
        root = self.fixture()
        for disposable in ("12_RUNTIME/agent_runs", ".brain-data", ".kb/ltm.sqlite"):
            self.assertFalse((root / disposable).exists())
        result = self.run_gate(root)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("absent by design", result.stdout)

    def test_a_missing_tracked_store_fails_and_names_the_plane(self):
        root = self.fixture()
        (root / "15_SYSTEM" / "memory" / "lessons.jsonl").unlink()
        result = self.run_gate(root)
        self.assertEqual(1, result.returncode)
        self.assertIn("error: tracked store missing: 15_SYSTEM/memory/lessons.jsonl",
                      result.stdout)

    def test_a_dropped_plane_fails(self):
        root = self.fixture()
        path = root / "15_SYSTEM" / "config" / "system.json"
        cfg = json.loads(path.read_text(encoding="utf-8"))
        del cfg["memory_planes"]["conversation"]
        path.write_text(json.dumps(cfg), encoding="utf-8")
        result = self.run_gate(root)
        self.assertEqual(1, result.returncode)
        self.assertIn("not mapped: conversation", result.stdout)

    def test_a_reader_that_points_at_nothing_fails(self):
        root = self.fixture()
        (root / "scripts" / "memory.py").unlink()
        result = self.run_gate(root)
        self.assertEqual(1, result.returncode)
        self.assertIn("error: reader does not exist: scripts/memory.py", result.stdout)

    def test_an_empty_tracked_folder_without_gitkeep_fails(self):
        root = self.fixture()
        for child in (root / "09_OPERATIONS" / "tasks").iterdir():
            child.unlink()
        result = self.run_gate(root)
        self.assertEqual(1, result.returncode)
        self.assertIn("empty folder with no .gitkeep", result.stdout)


if __name__ == "__main__":
    unittest.main()
