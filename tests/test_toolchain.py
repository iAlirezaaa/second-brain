"""Phase 2 tests: integrity toolchain against a synthetic fixture vault."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

GOOD_NOTE = """---
id: res-2026-10-27-good
type: resource
title: Good note
status: raw
owner: agent
topics: [testing]
created: 2026-10-27
updated: 2026-10-27
---
A note about [[understanding]].
"""

TARGET_NOTE = GOOD_NOTE.replace("res-2026-10-27-good", "res-2026-10-27-understanding").replace(
    "title: Good note", "title: Understanding").replace("[[understanding]].", "explained.")


def build_fixture(tmp, files):
    for name, content in files.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_script(script, vault):
    return subprocess.run([sys.executable, str(SCRIPTS / script), "--vault", str(vault)],
                          capture_output=True, text=True)


class TestTools(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_link_check_ok_when_target_exists(self):
        build_fixture(self.vault, {"a.md": GOOD_NOTE, "understanding.md": TARGET_NOTE})
        result = run_script("link_check.py", self.vault)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_link_check_catches_broken_link(self):
        build_fixture(self.vault, {"a.md": GOOD_NOTE})
        result = run_script("link_check.py", self.vault)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[[understanding]]", result.stdout)

    def test_frontmatter_check_ok(self):
        build_fixture(self.vault, {"a.md": GOOD_NOTE})
        result = run_script("frontmatter_check.py", self.vault)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_frontmatter_missing_field_fails(self):
        bad = GOOD_NOTE.replace("owner: agent\n", "")
        build_fixture(self.vault, {"a.md": bad})
        result = run_script("frontmatter_check.py", self.vault)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing field: owner", result.stdout)

    def test_frontmatter_bad_date_fails(self):
        bad = GOOD_NOTE.replace("created: 2026-10-27", "created: 27/10/2026")
        build_fixture(self.vault, {"a.md": bad})
        result = run_script("frontmatter_check.py", self.vault)
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad date format", result.stdout)

    def test_frontmatter_bad_enum_fails(self):
        bad = GOOD_NOTE.replace("owner: agent", "owner: robot")
        build_fixture(self.vault, {"a.md": bad})
        result = run_script("frontmatter_check.py", self.vault)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid owner", result.stdout)

    def test_vault_stats_counts_and_json(self):
        build_fixture(self.vault, {"00_Inbox/a.md": GOOD_NOTE})
        result = run_script("vault_stats.py", self.vault)
        self.assertEqual(result.returncode, 0)
        self.assertIn("00_Inbox: 1", result.stdout)
        json_result = subprocess.run(
            [sys.executable, str(SCRIPTS / "vault_stats.py"), "--vault", str(self.vault), "--json"],
            capture_output=True, text=True)
        self.assertEqual(json_result.returncode, 0)
        self.assertIn('"per_zone"', json_result.stdout)

    def test_shipped_template_is_clean(self):
        vault = ROOT / "vault-template"
        for script in ["link_check.py", "frontmatter_check.py"]:
            result = run_script(script, vault)
            self.assertEqual(result.returncode, 0, f"{script}: {result.stdout}")


if __name__ == "__main__":
    unittest.main()
